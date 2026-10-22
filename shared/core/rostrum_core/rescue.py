"""Open the last version that works (INTERACTION.md 1.19): a document file that is damaged, or saved by a newer
Rostrum, is refused in plain words (storage.open_doc). When its history file can still rebuild it, this replays the
history up to the last step that applies cleanly and opens that, and says which step it stopped at.

    plan(kind, folder, item)        what can be rebuilt, nothing written: a `Rebuilt` (step, steps, lost), or a
                                    RostrumError saying why not (no history, or its first line is unreadable)
    rebuild(kind, folder, item)     the same, then written: the damaged document and history are kept beside as
                                    "<name>.damaged-<time>" (never overwritten, never deleted), the rebuilt one saved
                                    in their place; returns (Document, Rebuilt)

A step is "clean" when its edits apply, its recorded `hash_after` matches, and the document passes the app's check.
Versions named after the stopping step are dropped (they pointed at steps that are gone from the rebuilt history).
"""
from __future__ import annotations

import copy
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from . import edits as E
from .document import Document
from .errors import RostrumError, codes
from .history import Change
from .storage import doc_hash, paths, save
from .tree import index


@dataclass
class Rebuilt:
    data: dict
    base: dict
    changes: list
    versions: dict
    step: int                 # the last step that applied cleanly (0: only how the document began)
    steps: int                # the steps the history file lists
    stamp: str = ""           # the "-<time>" the damaged files were kept under (set by rebuild)

    @property
    def lost(self) -> int:
        return self.steps - self.step

    def words(self) -> str:
        if not self.lost:
            return f"Rebuilt from its history: all {self.steps} steps."
        return f"Opened the last version that works: step {self.step} of {self.steps}. The {self.lost} after it could not be read."


def _read(path: Path, kind):
    """(base, [raw change dicts or None for a line that can't be read], versions), reading as far as it goes."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        head = json.loads(lines[0])
        if head.get("format") != kind.format:
            raise ValueError(f"it is a {head.get('format')!r} file")
        base = head["base"]
    except (OSError, IndexError, ValueError, KeyError, AttributeError) as e:
        raise RostrumError(codes.CHECK_FAILED, "rescue", str(path), f"can't rebuild it: its history's first line "
                           f"is unreadable ({type(e).__name__}: {e})", hint="Nothing was changed.") from e
    raw, versions = [], {}
    for line in lines[1:]:
        try:
            entry = json.loads(line)
            if "version" in entry and "seq" not in entry:
                versions[entry["version"]] = entry["at"]
            else:
                raw.append(entry)
        except (ValueError, KeyError, TypeError):
            raw.append(None)
    return base, raw, versions


def _replay(kind, base, changes):
    data = copy.deepcopy(base)
    idx = index(data, kind.lists)
    for c in changes:
        for e in c.edits:
            E.apply(data, kind.lists, e, f"step {c.seq}", idx)
    return data


def plan(kind, folder, item) -> Rebuilt:
    p = paths(folder, item, kind.ext)
    if not p["history"].is_file():
        raise RostrumError(codes.NOT_FOUND, "rescue", str(p["history"]), "is missing, so there is nothing to "
                           "rebuild it from", hint="Nothing was changed.")
    base, raw, versions = _read(p["history"], kind)
    good, data = [], copy.deepcopy(base)
    idx = index(data, kind.lists)
    for entry in raw:
        try:
            c = Change.from_dict(entry)
            for e in c.edits:
                E.apply(data, kind.lists, e, f"step {c.seq}", idx)
            if c.hash_after and doc_hash(data) != c.hash_after:
                raise ValueError("it doesn't add up")
        except Exception:  # noqa: BLE001  whatever is wrong with a step, the replay stops before it
            break
        good.append(c)
    if len(good) < len(raw):                                  # a step failed half-applied: start again from the base
        data = _replay(kind, base, good)
    while good and kind.problems(data):                       # a clean step can still leave a document that fails its check
        good.pop()
        data = _replay(kind, base, good)
    if kind.problems(data):
        raise RostrumError(codes.CHECK_FAILED, "rescue", str(p["history"]), "can't be rebuilt: even its first "
                           "step doesn't pass the document check", hint="Nothing was changed.")
    step = good[-1].seq if good else 0
    return Rebuilt(data, base, good, {n: s for n, s in versions.items() if s <= step}, step, len(raw))


def rebuild(kind, folder, item, cls=Document):
    r = plan(kind, folder, item)
    p = paths(folder, item, kind.ext)
    r.stamp = time.strftime("-%Y%m%d-%H%M%S")
    kept = []
    for key in ("doc", "history"):
        if p[key].exists():
            beside = p[key].with_name(f"{p[key].name}.damaged{r.stamp}")
            shutil.move(str(p[key]), str(beside))
            kept.append((p[key], beside))
    doc = cls(kind, copy.deepcopy(r.data), folder, item)
    doc.base = copy.deepcopy(r.base)
    for c in r.changes:
        doc.history.add(c)
    doc.history.versions = dict(r.versions)
    try:
        if p["script"].exists():                              # what scripts made last time: kept, not reset
            doc.script_bases = json.loads(p["script"].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass                                                  # a damaged script record only means the next re-run merges afresh
    try:
        save(doc)
    except Exception:
        for orig, beside in kept:                             # never leave the project with neither file
            if not orig.exists():
                shutil.move(str(beside), str(orig))
        raise
    return doc, r
