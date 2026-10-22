"""Find… for missing files (INTERACTION.md 1.19; no Qt, no app knowledge). A document opens even when some of the
files it uses are gone; those items show "missing". Find… asks for a folder and relinks every missing file found in it,
in ONE change (one apply, one undo step).

The app says what its document refers to, as `refs`: [(item id, field, path)], one per file an item uses (a layer's
"src", a clip's "file"). Then:

    missing(refs)                       the refs whose file is not on disk
    relink(refs, folder, op_of)         Relink: the operation calls that point each found file home, in the one list
                                        `doc.apply(calls, who, label=…)` takes; `op_of(item id)` names the app's
                                        "set the field" operation for that item (e.g. "layer.set"); `found` and
                                        `still_missing` say what happened, in words for the message line

A file is found by its name, else by its name ignoring capitals; several with the same name: the one whose folders
match the old path's the most. Folders starting with "." (the project's own .rostrum) are not searched.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from rostrum_core import RostrumError, codes

SEARCH_LIMIT = 200_000          # files looked at; a bigger folder is refused loudly, never half-searched


@dataclass
class Relink:
    calls: list = field(default_factory=list)
    found: list = field(default_factory=list)            # [(item id, field, old path, new path)]
    still_missing: list = field(default_factory=list)    # [(item id, field, path)]

    def words(self) -> str:
        n, left = len(self.found), len(self.still_missing)
        if not n:
            return "Found none of the missing files in that folder."
        tail = f" {left} still missing." if left else ""
        return f"Found {n} missing file{'s' if n != 1 else ''} and linked {'it' if n == 1 else 'them'} again.{tail}"


def missing(refs) -> list:
    return [r for r in refs if not Path(r[2]).exists()]


def _name(path: str) -> str:
    return str(path).replace("\\", "/").rsplit("/", 1)[-1]


def _index(folder: Path):
    exact, lower, seen = {}, {}, 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for f in sorted(files):
            seen += 1
            if seen > SEARCH_LIMIT:
                raise RostrumError(codes.BAD_ARGUMENT, "find", str(folder), f"has more than {SEARCH_LIMIT} files",
                                   hint="Pick a folder closer to where the files are. Nothing was changed.")
            p = Path(root) / f
            exact.setdefault(f, []).append(p)
            lower.setdefault(f.lower(), []).append(p)
    return exact, lower


def _closeness(candidate: Path, old: str) -> int:
    """How many folders, counting back from the file, the candidate shares with the old path."""
    a, b = [x.lower() for x in candidate.parts[::-1]], [x.lower() for x in str(old).replace("\\", "/").split("/")[::-1]]
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def relink(refs, folder, op_of) -> Relink:
    folder = Path(folder)
    if not folder.is_dir():
        raise RostrumError(codes.NOT_FOUND, "find", str(folder), "is not a folder", hint="Nothing was changed.")
    exact, lower = _index(folder)
    out = Relink()
    for item, fld, path in missing(refs):
        name = _name(path)
        options = exact.get(name) or lower.get(name.lower())
        if not options:
            out.still_missing.append((item, fld, path))
            continue
        best = max(options, key=lambda c: _closeness(c, path))      # (max keeps the first of equals: sorted, so stable)
        out.found.append((item, fld, path, str(best)))
        out.calls.append({"op": op_of(item), "target": [item], "args": {fld: str(best)}})
    return out
