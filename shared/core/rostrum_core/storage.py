"""Saving and opening a document (OPERATIONS.md § 6, project-service CONTRACT.md § 1).

In the project folder:
    docs/<item><ext>                    the document: {"format", "version", "saved_by", "at", "hash", ["uses",] "doc"}, compact
                                        JSON ("version" is the file format's number; "saved_by" the app version that
                                        wrote it, from the one VERSION file at the repo / install root; "at" the
                                        step it shows, "t" that step's clock time, "hash" its contents' hash: S39;
                                        "uses" the plugins it uses, id -> {"version", "api"}, written only when there
                                        are some and kept as read: plugin_parts.py)
    .rostrum/<item>.history.jsonl       the document when history began, then one line per change, appended
                                        (histfile.py has the layout)
    .rostrum/<item>.script.json         what each script produced last time (for the § 7 merge)

The history file is appended to (a crash mid-append cuts only its last line, left out loudly on open); the others are
written whole (temp file, then rename; retried while Windows holds the file). A live document (live.py) appends after
each change and writes the document file on Save, on close, and every live.FOLD_STEPS steps (a window: on its timer
once the person pauses, never inside a change), so the document file can be some steps behind (a program reading only
the document file sees the song as of its last write; use the history for the latest): opening takes it as
step "at" and plays the steps after it. A document file whose contents don't match its "hash" (or an old one without)
is checked against the whole history; one changed by something without history is recorded first as a change by
`outside`.

The pieces: storage_text (text, hash, paths, atomic write), storage_write (saving), and here the reading side. This
module stays the one door: every public name is importable from it.
"""
from __future__ import annotations

import copy
from pathlib import Path

from . import edits as E
from . import formats, histfile
from .errors import RostrumError, codes
from .kind import SHAPE_ERRORS
from .tree import index
from .who import UPGRADE, Who
from .storage_text import (VERSION_FILE, _read_json, _sha, app_version, canonical, canonical_pieces, doc_hash, paths,
                           write_atomic)
from .storage_write import Written, _append_to, _wrote, save, write_document

__all__ = ["VERSION_FILE", "Written", "app_version", "canonical", "canonical_pieces", "doc_hash", "open_doc", "paths",
           "read_history", "save", "write_atomic", "write_document"]


def read_history(path: Path, kind, start=0, changes=(), versions=None):
    """(Read, changes, versions) from a history file (from byte `start`, added to copies of `changes` / `versions`),
    or loudly refused (live.py reads it too)."""
    from .history import Change
    r = histfile.read(path, kind if start == 0 else None, start, app_version)
    changes, versions = list(changes), dict(versions or {})
    try:
        histfile.fold(r.entries, changes, versions, Change.from_dict)
        formats.fill(changes, kind)
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        raise RostrumError(codes.CHECK_FAILED, "open", str(path), f"is damaged ({type(e).__name__}: {e})",
                           hint="Nothing was saved over it.") from e
    return r, changes, versions


def open_doc(cls, folder, item, kind):
    """Opened whole or not at all: whatever was read, the result passes the document check (every field value,
    then the app's own), else the file is refused in words and never half-opened. A document file still exactly as
    Rostrum wrote it (its hash) held only checked contents: then only the items the steps after it set are checked."""
    p = paths(folder, item, kind.ext)
    doc, items = _read_doc(cls, folder, item, kind, p)
    if _upgrade(doc, kind, p["doc"]):
        items = None                                # brought up to date: everything is checked, not just the later steps
    problems = kind.problems(doc.data, items)
    if problems:
        raise RostrumError(codes.CHECK_FAILED, "open", str(p["doc"]), "is damaged: it doesn't hold together "
                           f"({'; '.join(problems[:3])}{' …' if len(problems) > 3 else ''})",
                           hint="Nothing was saved over it.")
    return doc


def _upgrade(doc, kind, path) -> bool:
    """An older file brought up to date before it is checked (so a rule that grew stricter never turns an old file
    away): the format's steps (DocKind.migrations) from the format the opened data is in, then the app's upgrade
    (DocKind.upgrade), recorded as one change by Rostrum carrying `format` [from, to] (formats.py), so it runs once per
    document: the next open reads the format from that step, whatever the document file's own number says. The
    history before it replays as written and nobody's undo takes it back. A file that can't be brought up to date is
    refused loudly, never opened half-converted. True when something changed."""
    note = formats.repair(doc)
    if note:
        doc.notes.append(note)
    try:
        data, labels = kind.bring_up(doc.data, doc.file_version, getattr(doc, "folder", None))
    except (*SHAPE_ERRORS, RostrumError) as e:
        raise RostrumError(codes.CHECK_FAILED, "open", str(path), f"can't be brought up to date: {type(e).__name__}: {e}",
                           hint="Nothing was saved over it.") from e
    if not labels:
        return bool(note)
    from .diff import diff
    doc.commit(data, diff(doc.data, data, kind.lists), UPGRADE, "; ".join(labels),
               format=[doc.file_version, kind.version] if doc.file_version < kind.version else None)
    doc.file_version = kind.version
    return True


def _as_written(text, file) -> bool:
    """The document file is as Rostrum wrote it (S39 on): its contents still match its own hash."""
    h, i = file.get("hash"), text.find(',"doc":')
    return bool(h) and ((i > 0 and _sha(text[i + 7:-1]) == h) or doc_hash(file["doc"]) == h)


def _at_step(file, changes) -> bool:
    """The file's step "at" is still in the history as it was (not replaced since by a nudge merged into it)."""
    at = file.get("at")
    return isinstance(at, int) and at <= len(changes) and (at == 0 or (
        changes[at - 1]._hash in ("", file["hash"]) and changes[at - 1].t == file.get("t")))


def _read_doc(cls, folder, item, kind, p):
    text, file = _read_json(p["doc"], "open")
    histfile.check_format(kind, file, p["doc"], app_version)
    if not p["history"].exists():
        doc = cls(kind, file["doc"], folder, item)
        doc.saved_by = file.get("saved_by")         # None: saved before files recorded it
        doc.file_version = file.get("version", 1)
        doc.uses = _uses(file, p["doc"])
        return doc, None
    r, changes, versions = read_history(p["history"], kind)
    written = _as_written(text, file)
    trusted = written and _at_step(file, changes)
    data, items = file["doc"], None
    if trusted:                                     # play only the steps after the document file's own
        from .run import changed_items
        idx, played = index(data, kind.lists), []
        for c in changes[file["at"]:]:
            played += [E.apply(data, kind.lists, e, f"step {c.seq}", idx) for e in c.edits]
        items = changed_items(played, idx, kind.lists)
    doc = cls(kind, data, folder, item, base=r.base)
    doc.saved_by, doc.notes = file.get("saved_by"), [r.torn] if r.torn else []
    doc.file_at = file.get("at") if trusted else None       # the step the document file shows (live.py folds the rest)
    doc.file_version = file.get("version", 1)
    doc.uses = _uses(file, p["doc"])
    for c in changes:
        doc.history.add(c)
    doc.history.versions = versions
    if p["script"].exists():
        doc.script_bases = _read_json(p["script"], "open")[1]
    replayed = doc.data if trusted else doc.at_step(doc.seq)
    last = changes[-1].hash_after if changes else ""
    if last and (not trusted or file["at"] < doc.seq) and doc_hash(replayed) != last:
        raise RostrumError(codes.CHECK_FAILED, "open", str(p["history"]), "doesn't add up to its own last step")
    if r.layout == histfile.LAYOUT:
        _wrote(doc, p["history"], r.end)
    if not written and doc_hash(replayed) != doc_hash(file["doc"]):
        _record_outside(doc, replayed, file["doc"], formats.after(doc.file_version, changes))
    else:
        doc.file_version = formats.after(doc.file_version, changes if not trusted else changes[file["at"]:])
        if not trusted:
            doc.data = replayed                   # Rostrum's own file, behind a step replaced since
    return doc, items


def _uses(file, path) -> dict:
    """The file's `uses` table (plugin id -> what it was saved with), kept as read; {} without one. Not a table: loud."""
    uses = file.get("uses", {})
    if not isinstance(uses, dict) or not all(isinstance(v, dict) for v in uses.values()):
        raise RostrumError(codes.CHECK_FAILED, "open", str(path), f"has a damaged plugin list (uses: {uses!r})",
                           hint="Nothing was saved over it.")
    return uses


def _record_outside(doc, replayed, on_disk, replayed_version):
    """The file was changed by something without history: record the difference first, then carry on. The data is
    then the file's own, in its format (the step says so when the history had taken it further: formats.py)."""
    from .diff import diff
    edits = diff(replayed, on_disk, doc.kind.lists)
    doc.data = copy.deepcopy(replayed)
    doc.commit(copy.deepcopy(on_disk), edits, Who.outside("file changed outside Rostrum"), "Changed outside Rostrum",
               format=[replayed_version, doc.file_version] if replayed_version != doc.file_version else None)
