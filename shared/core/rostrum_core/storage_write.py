"""Saving a document: append the history, write the script record and the document file (see storage.py)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from . import filestamps
from . import histfile
from .errors import RostrumError, codes
from .storage_text import _sha, app_version, canonical, paths, write_atomic


@dataclass
class Written:
    """Where this program last left the history file (wrote or read it): appending is safe while it still ends there."""
    ino: int
    size: int
    n: int                      # changes in the file
    last_t: float               # the last one's clock time (a nudge changes it: that step is appended again)
    versions: dict
    script: dict
    hashed: tuple = ()          # (seq, t, hash) of the last hash line written: a fold with nothing new adds none
    layout: int = histfile.LAYOUT   # an older layout is read (and its end known) but never appended to: rewritten whole


def save(doc, document=True, p=None):
    """Append the new steps to the history file (or write it whole: a new file, an old layout, one changed under us),
    then the script record if it changed, then (`document`) the document file. History first: a crash between them
    leaves a document file a few steps behind, which opening catches up. A step already in the file is written again
    only when it changed since (a person's nudge merged into it: its clock time moved). `p`: the document's paths()."""
    if doc.folder is None or doc.item_id is None:
        raise RostrumError(codes.BAD_ARGUMENT, "save", "the document", "has no project folder or item id")
    p, kind, ch = p or paths(doc.folder, doc.item_id, doc.kind.ext), doc.kind, doc.history.changes
    w, hist = doc._written, p["history"]
    body = h = None
    if document:
        kept = doc.kept                            # never an open preview's picture (Document.kept)
        body = canonical(kept)
        h = _sha(body)
        if ch and (ch[-1]._after is kept or ch[-1]._hash == h):
            ch[-1].hash_after = h                  # the last step's hash, known for free
    fh = _append_to(w, hist, len(ch))           # one handle: checked, cut, appended to and measured through it
    try:
        if fh is not None:
            text = histfile.change_line(ch[w.n - 1]) if w.n and ch[w.n - 1].t != w.last_t else ""
            text += "".join(histfile.change_line(c) for c in ch[w.n:])
            text += "".join(histfile.version_line(n, s) for n, s in doc.history.versions.items() if w.versions.get(n) != s)
        else:
            w, text = None, histfile.head(kind, doc.base) + "".join(histfile.change_line(c) for c in ch)
            text += "".join(histfile.version_line(n, s) for n, s in doc.history.versions.items())
        hashed = w.hashed if w is not None else ()
        if ch and h and ch[-1]._hash == h and hashed != (ch[-1].seq, ch[-1].t, h):
            text += histfile.hash_line(ch[-1].seq, h)
            hashed = (ch[-1].seq, ch[-1].t, h)
        if w is None:
            write_atomic(hist, text)
        elif text:
            if os.fstat(fh.fileno()).st_size != w.size:
                fh.truncate(w.size)               # a last line cut off by a crash goes before the next whole one
            fh.write(text.encode("utf-8"))        # appending: a seek-and-write handle cost ~6 ms per change on Windows
            fh.flush()
            filestamps.forget(hist)
        for c in ch[(w.n - 1 if w and w.n else 0):-1]:
            c._after = None                       # written without its hash: no tree kept for it
        if w is None or doc.script_bases != w.script:
            write_atomic(p["script"], json.dumps(doc.script_bases, indent=1, ensure_ascii=False))
        _wrote(doc, hist, st=os.fstat(fh.fileno()) if fh is not None else None, hashed=hashed)
    finally:
        if fh is not None:
            fh.close()
    if document:
        doc.saved_by = write_document(p["doc"], kind.format, kind.version, doc.seq, ch[-1].t if ch else 0.0, body, h,
                                      doc.uses)[1]


def write_document(path, format_, version, at, t, body, h=None, uses=None) -> tuple[str, str]:
    """Write the document file: `body` its canonical text, `h` its hash when known, `uses` the plugins it uses (left
    out when none). (hash, saved_by). Made only of plain values, so it may run on another thread (doc_write.py:
    hashing and writing let the screen's thread run)."""
    h = h or _sha(body)
    saved_by = app_version()
    head = {"format": format_, "version": version, "saved_by": saved_by, "at": at, "t": t, "hash": h}
    if uses:
        head["uses"] = uses
    top = json.dumps(head, ensure_ascii=False, separators=(",", ":"))
    write_atomic(path, f'{top[:-1]},"doc":{body}}}')
    return h, saved_by


def _append_to(w, hist, n):
    """The history file opened to append, when it is still the one we wrote last (same file, not shorter), else None
    (it is written whole). Asked through the handle: separate stats of the path cost a millisecond each per change."""
    if w is None or w.n > n or w.layout != histfile.LAYOUT:
        return None
    try:
        fh = open(hist, "ab")
    except FileNotFoundError:
        return None
    st = os.fstat(fh.fileno())
    if st.st_ino == w.ino and st.st_size >= w.size:
        return fh
    fh.close()
    return None


def _wrote(doc, hist, end=None, st=None, hashed=(), layout=histfile.LAYOUT):
    """Note where the history file ends now (after writing it; after reading it: `end`, before a cut-off line, and
    the `layout` read), so a look that finds it unchanged reads nothing, whoever's write it was.
    The script bases are copied shallow: a run replaces its base, never changes it in place (merge.py), so that tells
    a new one apart; a deep copy of every base cost milliseconds on every change."""
    st, ch = st or hist.stat(), doc.history.changes
    doc._written = Written(st.st_ino, st.st_size if end is None else end, len(ch), ch[-1].t if ch else 0.0,
                           dict(doc.history.versions), dict(doc.script_bases), hashed, layout)
