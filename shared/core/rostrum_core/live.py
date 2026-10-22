"""One document file shared live by several programs: the person's window and an agent's server (AGENTS.md rule 3).

Each program holds its own copy of the document. Without care, the last one to save wipes the other's steps.
`keep(doc)` makes every change go through one door instead:

    lock the file  →  catch up (take in the steps the other program saved)  →  make the change  →  save  →  unlock

so the history file only ever grows, whoever writes it. Between changes a window calls `catch_up()` on a timer (cheap:
it looks at the file's size and time first); each step it takes in arrives as an ordinary `Event("change", c)`, so the
screen shows an agent's work live and can tell who made it.

A step made from an older picture of the document (a person's drag that started before an agent's step landed) is
put on top of the newer document edit by edit when it is recorded (`Document.commit`). Steps on the same field by
someone else later are refused as always (history.py).
"""
from __future__ import annotations

import contextlib
import copy
import json

from .document import Event
from .history import History
from .storage import doc_hash, paths, read_history, save
from .tree import index
from . import edits as E
from .userhome import locked


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
        self.doc, self.p, self._depth = doc, paths(doc.folder, doc.item_id, doc.kind.ext), 0
        self._stamp = None

    def _now_stamp(self):
        try:
            st = self.p["history"].stat()
            return st.st_mtime_ns, st.st_size
        except FileNotFoundError:
            return None

    def _mine(self):
        h = self.doc.history
        return h.seq, h.changes[-1].hash_after if h.changes else "", dict(h.versions)

    @contextlib.contextmanager
    def door(self):
        """Held around one change (re-entrant: undo inside a run of steps takes it once). Yields the steps caught up
        on entry, so a change planned on an older picture knows to rebase."""
        if self._depth:
            yield []
            return
        with locked(self.p["history"], "save", "another Rostrum program (a window or an agent)"):
            self._depth += 1
            try:
                caught = self.catch_up()
                before = self._mine()
                yield caught
                if self._mine() != before or self._stamp is None:
                    save(self.doc)
                    self._stamp = self._now_stamp()
            finally:
                self._depth -= 1

    def catch_up(self) -> list:
        """Take in what another program saved since we last looked; return those steps (oldest first). A window's
        timer and every door call it. Nothing happens during a person's drag (it is caught up when the drag ends)."""
        doc = self.doc
        stamp = self._now_stamp()
        if stamp is None or stamp == self._stamp or doc._gesture is not None:
            return []
        base, changes, versions = read_history(self.p["history"], doc.kind)
        self._stamp = stamp
        n = doc.history.seq
        ours = doc.history.changes[-1] if n else None
        same_line = len(changes) >= n and (n == 0 or (changes[n - 1].hash_after == ours.hash_after
                                                       and changes[n - 1].t == ours.t))
        new = self._ahead(changes[n:]) if same_line else None
        if new is None:                                  # parted lines, or steps that don't add up: read it whole
            new = self._reload(base, changes)
        doc.history.versions = versions
        if self.p["script"].exists():
            doc.script_bases = json.loads(self.p["script"].read_text(encoding="utf-8"))
        for c in new:
            doc._emit(Event("change", c))
        return new

    def _ahead(self, new):
        """The file has our steps and then `new`: apply them on a copy; None if they don't add up to the file."""
        doc = self.doc
        if not new:
            return []
        work = copy.deepcopy(doc.data)
        idx = index(work, doc.kind.lists)
        for c in new:
            for e in c.edits:
                E.apply(work, doc.kind.lists, e, f"step {c.seq}", idx)
        if doc_hash(work) != new[-1].hash_after:
            return None
        doc.data = work
        for c in new:
            doc.history.add(c)
        return new

    def _reload(self, base, changes) -> list:
        """The file's line and ours parted (a nudge merged in place, a rewrite): take the file's whole history."""
        doc = self.doc
        old = {c.seq: (c.hash_after, c.t) for c in doc.history.changes}
        doc.base, doc.history = base, History(doc.kind.lists)
        for c in changes:
            doc.history.add(c)
        doc.data = doc.at_step(doc.seq)
        doc._emit(Event("reset"))
        return [c for c in changes if old.get(c.seq) != (c.hash_after, c.t)]
