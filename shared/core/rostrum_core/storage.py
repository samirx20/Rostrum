"""Saving and opening a document (OPERATIONS.md § 6, project-service CONTRACT.md § 1).

In the project folder:
    docs/<item><ext>                    the document: {"format", "version", "saved_by", "at", "hash", "doc"}, compact
                                        JSON ("version" is the file format's number; "saved_by" the app version that
                                        wrote it, from the one VERSION file at the repo / install root; "at" the
                                        step it shows, "t" that step's clock time, "hash" its contents' hash: S39)
    .rostrum/<item>.history.jsonl       the document when history began, then one line per change, appended
                                        (histfile.py has the layout)
    .rostrum/<item>.script.json         what each script produced last time (for the § 7 merge)

The history file is appended to (a crash mid-append cuts only its last line, left out loudly on open); the others are
written whole (temp file, then rename; retried while Windows holds the file). A live document (live.py) appends after
each change and writes the document file on Save, on close and every live.FOLD_STEPS steps, so the document file can be
some steps behind (a program reading only the document file sees the song as of its last write; use the history for the
latest): opening takes it as
step "at" and plays the steps after it. A document file whose contents don't match its "hash" (or an old one without)
is checked against the whole history; one changed by something without history is recorded first as a change by
`outside`.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from . import edits as E
from . import histfile
from .errors import RostrumError, codes
from .kind import SHAPE_ERRORS
from .tree import index
from .who import Who

VERSION_FILE = Path(__file__).resolve().parents[3] / "VERSION"   # <root>/shared/core/rostrum_core/storage.py


def app_version() -> str:
    """The Rostrum version saving files (the installer's and Help → About's number too). Missing is loud."""
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise RostrumError(codes.INTERNAL, "save", str(VERSION_FILE), f"can't be read ({e})",
                           hint="The app's VERSION file is missing; reinstall Rostrum.") from e


def canonical(data) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def doc_hash(data) -> str:
    return _sha(canonical(data))


def paths(folder, item, ext) -> dict:
    folder = Path(folder)
    return {"doc": folder / "docs" / f"{item}{ext}", "history": folder / ".rostrum" / f"{item}.history.jsonl",
            "script": folder / ".rostrum" / f"{item}.script.json"}


def write_atomic(path: Path, text: str, tries: int = 20):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.partial")   # one per writer: no collisions
    tmp.write_text(text, encoding="utf-8")
    for n in range(tries):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:          # Windows: someone has the file open; wait a little
            if n == tries - 1:
                raise RostrumError(codes.INTERNAL, "save", str(path), "stayed locked by another program",
                                   hint=f"The new version is kept at {tmp}.")
            time.sleep(0.1)


@dataclass
class Written:
    """Where this program last left the history file (wrote or read it): appending is safe while it still ends there."""
    ino: int
    size: int
    n: int                      # changes in the file
    last_t: float               # the last one's clock time (a nudge changes it: that step is appended again)
    versions: dict
    script: dict


def save(doc, document=True):
    """Append the new steps to the history file (or write it whole: a new file, an old layout, one changed under us),
    then the script record if it changed, then (`document`) the document file. History first: a crash between them
    leaves a document file a few steps behind, which opening catches up."""
    if doc.folder is None or doc.item_id is None:
        raise RostrumError(codes.BAD_ARGUMENT, "save", "the document", "has no project folder or item id")
    p, kind, ch = paths(doc.folder, doc.item_id, doc.kind.ext), doc.kind, doc.history.changes
    w, hist = doc._written, p["history"]
    body = h = None
    if document:
        body = canonical(doc.data)
        h = _sha(body)
        if ch and (ch[-1]._after is doc.data or ch[-1]._hash == h):
            ch[-1].hash_after = h                  # the last step's hash, known for free
    if _appendable(w, hist, len(ch)):
        text = histfile.change_line(ch[w.n - 1]) if w.n and ch[w.n - 1].t != w.last_t else ""
        text += "".join(histfile.change_line(c) for c in ch[w.n:])
        text += "".join(histfile.version_line(n, s) for n, s in doc.history.versions.items() if w.versions.get(n) != s)
    else:
        w, text = None, histfile.head(kind, doc.base) + "".join(histfile.change_line(c) for c in ch)
        text += "".join(histfile.version_line(n, s) for n, s in doc.history.versions.items())
    if ch and h and ch[-1]._hash == h:
        text += histfile.hash_line(ch[-1].seq, h)
    if w is None:
        write_atomic(hist, text)
    elif text:
        if hist.stat().st_size != w.size:
            os.truncate(hist, w.size)             # a last line cut off by a crash goes before the next whole one
        with open(hist, "ab") as fh:              # appending: a seek-and-write handle cost ~6 ms per change on Windows
            fh.write(text.encode("utf-8"))
    for c in ch[(w.n - 1 if w and w.n else 0):-1]:
        c._after = None                           # written without its hash: no tree kept for it
    if w is None or doc.script_bases != w.script:
        write_atomic(p["script"], json.dumps(doc.script_bases, indent=1, ensure_ascii=False))
    _wrote(doc, hist)
    if document:
        saved_by = app_version()
        top = json.dumps({"format": kind.format, "version": kind.version, "saved_by": saved_by, "at": doc.seq,
                          "t": ch[-1].t if ch else 0.0, "hash": h}, ensure_ascii=False, separators=(",", ":"))
        write_atomic(p["doc"], f'{top[:-1]},"doc":{body}}}')
        doc.saved_by = saved_by


def _appendable(w, hist, n) -> bool:
    if w is None or w.n > n:
        return False
    try:
        st = hist.stat()
    except FileNotFoundError:
        return False
    return st.st_ino == w.ino and st.st_size >= w.size


def _wrote(doc, hist, end=None):
    """Note where the history file ends now (after writing it; after reading it: `end`, before a cut-off line).
    The script bases are copied shallow: a run replaces its base, never changes it in place (merge.py), so that tells
    a new one apart; a deep copy of every base cost milliseconds on every change."""
    st, ch = hist.stat(), doc.history.changes
    doc._written = Written(st.st_ino, st.st_size if end is None else end, len(ch), ch[-1].t if ch else 0.0,
                           dict(doc.history.versions), dict(doc.script_bases))


def _read_json(path: Path, where: str):
    try:
        text = path.read_text(encoding="utf-8")
        return text, json.loads(text)
    except (OSError, json.JSONDecodeError) as e:
        raise RostrumError(codes.CHECK_FAILED, where, str(path), f"can't be read: {e}") from e


def read_history(path: Path, kind, start=0, changes=(), versions=None):
    """(Read, changes, versions) from a history file (from byte `start`, added to copies of `changes` / `versions`),
    or loudly refused (live.py reads it too)."""
    from .history import Change
    r = histfile.read(path, kind if start == 0 else None, start, app_version)
    changes, versions = list(changes), dict(versions or {})
    try:
        histfile.fold(r.entries, changes, versions, Change.from_dict)
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
    away): the format's steps (DocKind.migrations) from the file's own number, then the app's upgrade (DocKind.upgrade),
    recorded as one change by Rostrum so the history before it replays as written and undo takes it back. A file that
    can't be brought up to date is refused loudly, never opened half-converted. True when something changed."""
    try:
        data, labels = kind.migrate(doc.data, doc.file_version, getattr(doc, "folder", None))
        up = kind.upgrade(data, kind.lists, getattr(doc, "folder", None)) if kind.upgrade else None
    except (*SHAPE_ERRORS, RostrumError) as e:
        raise RostrumError(codes.CHECK_FAILED, "open", str(path), f"can't be brought up to date: {type(e).__name__}: {e}",
                           hint="Nothing was saved over it.") from e
    if up is not None:
        data, label = up
        labels.append(label)
    if not labels:
        return False
    from .diff import diff
    doc.commit(data, diff(doc.data, data, kind.lists), Who.outside("Rostrum (older file)"), "; ".join(labels))
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
        return doc, None
    r, changes, versions = read_history(p["history"], kind)
    written = _as_written(text, file)
    trusted = written and _at_step(file, changes)
    data, items = file["doc"], None
    if trusted:                                     # play only the steps after the document file's own
        from .run import _changed
        idx, played = index(data, kind.lists), []
        for c in changes[file["at"]:]:
            played += [E.apply(data, kind.lists, e, f"step {c.seq}", idx) for e in c.edits]
        items = _changed(played, idx, kind.lists)
    doc = cls(kind, data, folder, item, base=r.base)
    doc.saved_by, doc.notes = file.get("saved_by"), [r.torn] if r.torn else []
    doc.file_version = file.get("version", 1)
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
        _record_outside(doc, replayed, file["doc"])
    elif not trusted:
        doc.data = replayed                       # Rostrum's own file, behind a step replaced since
    return doc, items


def _record_outside(doc, replayed, on_disk):
    """The file was changed by something without history: record the difference first, then carry on."""
    from .diff import diff
    edits = diff(replayed, on_disk, doc.kind.lists)
    doc.data = copy.deepcopy(replayed)
    doc.commit(copy.deepcopy(on_disk), edits, Who.outside("file changed outside Rostrum"), "Changed outside Rostrum")
