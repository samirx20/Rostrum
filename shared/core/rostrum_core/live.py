"""One document file shared live by several programs: the person's window and an agent's server (AGENTS.md rule 3).

Each program holds its own copy of the document. Without care, the last one to save wipes the other's steps.
`keep(doc)` makes every change go through one door instead:

    lock the file  →  catch up (take in the steps the other program saved)  →  make the change  →  save  →  unlock

so the history file only ever grows, whoever writes it (each change is one line appended). Between changes a window calls
`catch_up()` on a timer (cheap: it looks at the file's size first, then reads only the new lines); each step it takes in arrives as an ordinary `Event("change", c)`, so the
screen shows an agent's work live and can tell who made it.

A step made from an older picture of the document (a person's drag that started before an agent's step landed) is
put on top of the newer document edit by edit when it is recorded (`Document.commit`). Steps on the same field by
someone else later are refused as always (history.py).

The document file (the whole song, written in one go) is not written on every change: the history file is the truth
(opening plays whatever the document file lacks, so a crash at any moment loses nothing the history holds). It is
brought up to date ("folded"):
  - by Save, when the window closes, and by the first door of a new document;
  - in a program without a window (an agent's server, a script): in the door, every FOLD_STEPS steps;
  - in a window (`windowed()`, the kit's LiveLink): never inside a change, so no click or drag pays for writing the
    whole song; the link's timer calls `fold_if_quiet()` between pointer actions, which folds once the person has
    paused FOLD_QUIET_S, or at once when the file is FOLD_STEPS steps behind. That fold never holds the person up:
    its text is made a slice at a time between events (`fold_work`) and written on a thread of its own (doc_write.py);
    the next tick hears how it went, and a failed write is said loudly (and tried again). Save and close finish a
    write in progress, then write what is newer, so quitting always completes.
So a reader of the document file alone sees the song at most FOLD_STEPS steps old (in a window: plus the steps made
within one tick of its timer), and the latest within FOLD_QUIET_S of the person pausing.
"""
from __future__ import annotations

import contextlib
import json
import time

from .document import Event
from .errors import RostrumError, codes
from .history import History
from .histfile import LAYOUT
from .doc_write import DocWrite
from .storage import _wrote, doc_hash, paths, read_history, save
from . import edits as E
from .userhome import locked


FOLD_STEPS = 20       # the document file is brought up to date at least this often (steps behind the history file)
FOLD_QUIET_S = 1.0    # a window folds once the person has made no change for this long (fold_if_quiet)


def keep(doc) -> "Live":
    """Make `doc` (saved in a project folder) live: every change is locked, caught up and saved at once. A document
    already live stays as it is (the kit's file model and the window's bridge both ask)."""
    if doc.folder is None or doc.item_id is None:
        raise ValueError("live.keep needs a document saved in a project folder")
    if doc.live is not None:
        return doc.live
    live = doc.live = Live(doc)
    with live.door():                       # first save (a new document) and first look
        pass
    return live


class Live:
    def __init__(self, doc):
        self.doc, self.p, self._depth, self._started = doc, paths(doc.folder, doc.item_id, doc.kind.ext), 0, False
        self._filed = doc.seq                    # the step the document file last got from us (or was at when we began)
        self._filed_data = doc.data if doc.file_at == doc.seq else None   # the tree the file holds (never changed
                                                 # in place: `is` tells); None: behind or unknown, folded when quiet
        self._doc_there = False                  # the document file is known to be there (we wrote it, or saw it)
        self._windowed = False                   # a window folds on its own timer, never inside a change
        self._changed_at = 0.0                   # time.monotonic() of the last change saved through the door
        self._writing = None                     # a document-file write in progress (doc_write.DocWrite)

    def _mine(self):
        h = self.doc.history
        return h.changes[-1].ident() if h.changes else None, dict(h.versions)

    @contextlib.contextmanager
    def door(self):
        """Held around one change (re-entrant: undo inside a run of steps takes it once). Yields the steps caught up
        on entry, so a change planned on an older picture knows to rebase. A change appends its own line to the
        history file (a small cost that never grows with the song); the whole document file only as the module
        docstring says."""
        if self._depth:
            yield []
            return
        with locked(self.p["history"], "save", "another Rostrum program (a window or an agent)"):
            self._depth += 1
            try:
                caught = self.catch_up()
                before = self._mine()
                yield caught
                first = not self._started and not (self.p["history"].exists() and self.p["doc"].exists())
                if self._mine() != before or first:     # a first look at a saved document writes nothing
                    behind = not self._windowed and self.doc.seq - self._filed >= FOLD_STEPS
                    whole = first or behind or not self._doc_there and not self.p["doc"].exists()
                    save(self.doc, document=whole, p=self.p)
                    self._doc_there = True                  # (asked of the disk once, not on every change)
                    if whole:
                        self._filed, self._filed_data = self.doc.seq, self.doc.data
                    self._changed_at = time.monotonic()
                self._started = True
            finally:
                self._depth -= 1

    def windowed(self):
        """A window holds this document: from now on its document file is written on the window's timer
        (`fold_if_quiet`), on Save and on close, never inside a change (the kit's LiveLink says so)."""
        self._windowed = True

    def behind(self) -> bool:
        """The document file lacks something this program holds (a step of its own, or one taken in)."""
        return self.doc.data is not self._filed_data

    def fold(self, always=True):
        """Write the document file now, through the door (lock, catch up): Save and close (`always`), or only when
        it is behind. A background write still going is waited for first (a failed one is written again here)."""
        if self._writing is not None:
            self._writing.finish()                  # (its failure is not raised: this write replaces it)
            self._collect(raise_=False)
        with self.door():
            if always or self.behind():
                save(self.doc, p=self.p)
                self._filed, self._filed_data, self._doc_there = self.doc.seq, self.doc.data, True

    def fold_if_quiet(self) -> bool:
        """A window's timer, between pointer actions: fold once the person has paused FOLD_QUIET_S, or at once when
        the file is FOLD_STEPS steps behind. Never during a drag (the document holds the drag's unsaved picture
        then). True when it folded."""
        self._collect()
        if self._writing is not None or not self.behind() or self.doc._gesture is not None:
            return False
        if time.monotonic() - self._changed_at < FOLD_QUIET_S and self.doc.seq - self._filed < FOLD_STEPS:
            return False
        with self.door():                           # lock, catch up, history appended: then the tree as it stands
            if not self.behind():
                return False
            ch = self.doc.history.changes
            self._writing = DocWrite(self.p["doc"], self.doc.kind, self.doc.data, self.doc.seq, ch[-1] if ch else None,
                                     self.doc.uses)
        return True

    def fold_work(self, budget=0.003) -> bool:
        """Carry a fold started by fold_if_quiet on by about `budget` seconds of the window's thread (its link calls
        this from a zero timer, so events run between slices). True while there is more to do."""
        return self._writing is not None and self._writing.step(budget)

    def _collect(self, raise_=True):
        """Take in a finished background write: the file is up to date with its tree, or (`raise_`) it failed, loudly
        in words, and the next quiet tick writes again (nothing is lost: every step is in the history file)."""
        w = self._writing
        if w is None or not w.done():
            return
        self._writing = None
        data, last = w.data, w.last
        err = w.error()
        if err is None:
            h, self.doc.saved_by = w.result()
            self._filed, self._filed_data, self._doc_there = w.seq, data, True
            if last is not None and last._after is data:
                last.hash_after = h                 # its hash, known for free (the next history line carries it)
        elif raise_:
            raise RostrumError(codes.INTERNAL, "save", str(self.p["doc"]), f"could not be written ({err})",
                               hint="Every change is kept in the history file; Rostrum tries again in a moment.",
                               plain="Your work could not be written to its file just now. Nothing is lost; "
                                     "Rostrum will try again.") from err

    def settle(self):
        """Wait for a background write of the document file and take it in (a failure raises): a script or a check
        that reads the file right after a fold."""
        if self._writing is not None:
            self._writing.finish()
            self._collect()

    def catch_up(self) -> list:
        """Take in what another program saved since we last looked; return those steps (oldest first). A window's
        timer and every door call it. Nothing happens during a person's drag (it is caught up when the drag ends).
        Cheap: the file's size first, then only the lines added since (the whole file if it was rewritten)."""
        doc, hist, w = self.doc, self.p["history"], self.doc._written
        try:
            st = hist.stat()
        except FileNotFoundError:
            return []
        if doc._gesture is not None or (w is not None and (st.st_ino, st.st_size) == (w.ino, w.size)):
            return []
        tail = w is not None and st.st_ino == w.ino and st.st_size > w.size
        if tail:
            r, changes, versions = read_history(hist, doc.kind, w.size, doc.history.changes, doc.history.versions)
            if r.end == w.size:
                return []                                # only a line another program is still writing
        else:
            r, changes, versions = read_history(hist, doc.kind)
        n = doc.history.seq
        ours = doc.history.changes[-1] if n else None
        same_line = len(changes) >= n and (n == 0 or changes[n - 1].ident() == ours.ident())
        new = self._ahead(changes[n:]) if same_line else None
        if new is None:                                  # parted lines, or steps that don't add up: read it whole
            new = self._reload(None if tail else r.base, changes)
        doc.history.versions = versions
        if self.p["script"].exists():
            doc.script_bases = json.loads(self.p["script"].read_text(encoding="utf-8"))
        _wrote(doc, hist, r.end)
        if r.layout != LAYOUT and not tail:
            doc._written = None                          # an old layout: the next save writes it whole, new layout
        for c in new:
            doc._emit(Event("change", c))
        return new

    def _ahead(self, new):
        """The file has our steps and then `new`: apply them on a copy; None if they don't add up to the file."""
        doc = self.doc
        if not new:
            return []
        work, idx = E.fork(doc.data, doc.kind.lists, doc._index())
        for c in new:
            for e in c.edits:
                E.apply(work, doc.kind.lists, e, f"step {c.seq}", idx)
        if new[-1].hash_after and doc_hash(work) != new[-1].hash_after:
            return None
        doc.data = work
        doc._indexed(work, idx)
        for c in new:
            doc.history.add(c)
        return new

    def _reload(self, base, changes) -> list:
        """The file's line and ours parted (a nudge merged in place, a rewrite): take the file's whole history."""
        doc = self.doc
        old = {c.seq: c.ident() for c in doc.history.changes}
        if base is not None:
            doc.base = base
        doc.history = History(doc.kind.lists)
        for c in changes:
            doc.history.add(c)
        doc.data = doc.at_step(doc.seq)
        doc._emit(Event("reset"))
        return [c for c in changes if old.get(c.seq) != c.ident()]
