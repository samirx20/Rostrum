"""The history file, `.rostrum/<item>.history.jsonl`: appended to after each change, never rewritten (S39).

Layout 2 (written since S39):
    line 1   {"format", "version", "layout": 2}
    line 2   {"base": the document when history began}      read only when needed (versions, rescue, an outside edit)
    then, appended, one line each:
        a change          {"seq", "who", "edits", ...}     the same seq as the line before = it replaces that step
                                                           (a person's nudge merged into their last step)
        a named version   {"version": name, "at": seq}
        a checked hash    {"hash": h, "at": seq}           the document's hash after step `at` (written with the
                                                           document file, so opening can trust that file)
Layout 1 (before S39, read only; the next save writes layout 2): line 1 {"format", "version", "base"}, then changes
and versions, the whole file rewritten on every save.

A last line with no line end is a crash mid-append: it is left out with a warning (never silently, never the rest)
and cut off before the next append. Any other line that can't be read refuses the file, naming the line.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .errors import RostrumError, codes

LAYOUT = 2
log = logging.getLogger("rostrum.history")


def _line(d) -> str:
    return json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n"


def head(kind, base) -> str:
    return _line({"format": kind.format, "version": kind.version, "layout": LAYOUT}) + _line({"base": base})


def change_line(c) -> str:
    return _line(c.to_dict())


def version_line(name, at) -> str:
    return _line({"version": name, "at": at})


def hash_line(at, h) -> str:
    return _line({"hash": h, "at": at})


def check_format(kind, head_, path, app_version):
    if head_.get("format") != kind.format:
        raise RostrumError(codes.BAD_ARGUMENT, "open", str(path), f"is a {head_.get('format')!r} file", [kind.format])
    if head_.get("version", 0) > kind.version:
        by = f"Rostrum {head_['saved_by']}, " if isinstance(head_.get("saved_by"), str) else ""
        raise RostrumError(codes.CHECK_FAILED, "open", str(path), f"was saved by a newer version ({by}file format "
                           f"{head_['version']}; this is Rostrum {app_version()}, format {kind.version})",
                           hint="Update Rostrum to open it.")


@dataclass
class Read:
    """What one read of the file gave: entries ("change" | "version" | "hash", dict | None) from `start` to `end`
    (the byte after the last whole line), the base (layout 1: the dict; layout 2: its line, parsed on demand)."""
    entries: list = field(default_factory=list)
    end: int = 0
    torn: str = ""                   # plain words about a cut-off last line, "" when there was none
    layout: int = LAYOUT
    version: int = 1                 # the file format the head names (the base's, when history began)
    _base: object = None

    def base(self):
        if isinstance(self._base, str):
            self._base = json.loads(self._base)["base"]
        return self._base


def read(path: Path, kind=None, start=0, app_version=None, lenient=False) -> Read:
    """Read from byte `start` (0: the whole file, its head checked against `kind`). `lenient` (rescue): a line that
    can't be read is an entry (None) instead of a refusal."""
    with open(path, "rb") as fh:
        fh.seek(start)
        raw = fh.read()
    r = Read(end=start + len(raw))
    if raw and not raw.endswith(b"\n"):
        cut = raw.rfind(b"\n") + 1
        r.end, raw = start + cut, raw[:cut]
        if start == 0:                       # a tail read can meet another program's line half-written: not news
            r.torn = f"{path}: the last step was cut off by a crash while saving and was left out; the rest opened"
            log.warning(r.torn)
    lines = raw.decode("utf-8").split("\n")[:-1]
    n0 = 1
    if start == 0:
        n0 = _head(r, lines, path, kind, app_version, lenient)
        lines = lines[n0 - 1:]
    for n, text in enumerate(lines, n0):
        try:
            e = json.loads(text)
            r.entries.append(("change" if "seq" in e else "version" if "version" in e else
                              "hash" if "hash" in e else _unknown(e), e))
        except (json.JSONDecodeError, ValueError, TypeError) as err:
            if not lenient:
                raise RostrumError(codes.CHECK_FAILED, "open", f"{path} line {n}",
                                   f"is damaged ({type(err).__name__}: {err})", hint="Nothing was saved over it.") from err
            r.entries.append(("change", None))
    return r


def _unknown(e):
    raise ValueError(f"not a step, a version or a hash: {list(e)[:4]}")


def _head(r, lines, path, kind, app_version, lenient) -> int:
    """Check line 1; set the base; return the first entry's line number."""
    try:
        h = json.loads(lines[0])
        if kind is not None:
            check_format(kind, h, path, app_version)
        r.version = h.get("version", 1)
        if "base" in h:
            r.layout, r._base = 1, h["base"]
            return 2
        r.layout, r._base = h["layout"], lines[1]
        if not lines[1].startswith('{"base":'):
            raise ValueError("line 2 isn't the starting document")
        return 3
    except RostrumError:
        raise
    except (IndexError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise RostrumError(codes.CHECK_FAILED, "rescue" if lenient else "open", f"{path} line 1",
                           f"is damaged ({type(e).__name__}: {e})", hint="Nothing was saved over it.") from e


def fold(entries, changes: list, versions: dict, from_dict) -> None:
    """Add read entries to `changes` / `versions` in place (a repeated seq replaces the step, a hash fills one in)."""
    for kind_, e in entries:
        if kind_ == "version":
            versions[e["version"]] = e["at"]
        elif kind_ == "hash":
            at = e["at"]
            if 0 < at <= len(changes) and changes[at - 1].seq == at:
                changes[at - 1].hash_after = e["hash"]
        else:
            c = from_dict(e)
            last = changes[-1].seq if changes else 0
            if c.seq == last and last:
                changes[-1] = c
            elif c.seq == last + 1:
                changes.append(c)
            else:
                raise KeyError(f"step {c.seq} follows step {last}")
