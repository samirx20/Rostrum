"""History, versions and agent review for QML (a slot mix-in for DocBridge, see parts.py): the History sheet's rows,
Undo all / Bring back for an agent's run, Undo this for one step, named versions, and what ↶ ↷ would do.

Every action is a new change by the person (undo is a step too; History only grows) and every refusal goes
through `_guard` to the message line in words. The core refuses an undo when someone changed the same thing later.
The Qt properties (`undoLabel`, `redoLabel`, `versions`, `agent`) are declared on DocBridge (a plain mix-in can't
carry Qt properties); their reads live here.
"""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_core import RostrumError, codes

from . import history_rows
from .parts import SlotMixin


class ReviewSlots(SlotMixin):
    # ---- reads ------------------------------------------------------------------------------------------------
    @Slot(str, result="QVariantList")
    def historyRows(self, show):
        """History's rows, newest first; `show`: "everyone" | "you" | "agents" | "scripts" (history_rows.py)."""
        return history_rows.rows(self._review_docs(), self.who, show or "everyone")

    def versions_list(self):
        return history_rows.versions(self.doc)

    def next_undo_label(self) -> str:
        """What ↶ would take back ("" = nothing: the button is absent). The same pick as desk.undo."""
        hit = self._next_step(lambda h: h.last_undoable(self.who), redo=False)
        return hit.label if hit else ""

    def next_redo_label(self) -> str:
        hit = self._next_step(lambda h: h.last_redoable(self.who), redo=True)
        return hit.label if hit else ""

    def _next_step(self, pick, redo):
        """The change desk.undo / desk.redo would act on across the document and its partners, or None."""
        hs = [d.history for d in self._review_docs()]
        found = [(h.acted(c), c) for h in hs for c in [pick(h)] if c is not None]
        if not found:
            return None
        at, c = max(found, key=lambda f: f[0])
        if redo and at < max((x.t for h in hs for x in h.changes if x.original and x.who == self.who), default=0.0):
            return None
        return c

    def _review_docs(self):
        """The document, then each joined partner that has a document now (rows' `doc` indexes this list)."""
        return [self.doc] + [d for d in (p.history_doc() for p in self._kit.partners) if d is not None]

    # ---- agent runs and steps -----------------------------------------------------------------------------------
    @Slot(str, result=bool)
    def undoRun(self, session):
        """Undo all: the person takes back a whole agent run in ONE step per document it touched."""
        return self._guard(lambda: self._each_doc(lambda d: d.undo_session(session, self.who), session, "Undid"))

    @Slot(str, result=bool)
    def redoRun(self, session):
        """Bring back an agent run the person took back (core: Document.redo_session)."""
        return self._guard(lambda: self._each_doc(lambda d: d.redo_session(session, self.who), session, "Brought back"))

    def _each_doc(self, act, session, verb):
        made = [(d, c) for d in self._review_docs() for c in [act(d)] if c is not None]
        if not made:
            raise RostrumError(codes.CONFLICT, "history", "that run", "has nothing left to change",
                               hint="It may already be taken back or brought back.")
        self._stepped([d for d, _ in made])
        n = sum(len(c.undoes) + len(c.redoes) for _, c in made)
        who = self._run_who(session)
        self._set_status(f"{verb}: {who}'s {n} change{'s' if n != 1 else ''}")
        if verb == "Undid":
            self._kit.agent.forget(session)

    def _run_who(self, session) -> str:
        for d in self._review_docs():
            for c in d.history.changes:
                if c.session == session and c.original:
                    return history_rows.who_name(c.who, self.who)
        return "the agent"

    @Slot(int, int, result=bool)
    def undoStep(self, seq, doc):
        """Undo this: one step (`seq` in document `doc`, a row's fields) taken back, whoever made it."""
        def go():
            d = self._review_docs()[doc]
            c = d.undo_changes([d.history.get(seq)], self.who)
            self._stepped([d])
            self._set_status(c.label)                # "Undid: <label>"
        return self._guard(go)

    def _stepped(self, docs):
        """A partner (the markers) saves and re-reads after a step there (bridge_edits._step does the same)."""
        for p in self._kit.partners:
            if p.history_doc() in docs:
                p.stepped(p.history_doc())

    # ---- versions ---------------------------------------------------------------------------------------------
    @Slot(str, result=bool)
    def saveVersion(self, name):
        """Save a version: a name for the document as it is now (saved to disk when it has a folder)."""
        def go():
            n = name.strip()
            if not n:
                raise RostrumError(codes.BAD_ARGUMENT, "save version", "the name", "is empty",
                                   hint="Type a name for the version.")
            self.doc.mark_version(n)
            if self.doc.folder is not None:
                self.doc.save()
            self._set_status(f'Saved version "{n}"')
            self.docChanged.emit()
        return self._guard(go)

    @Slot(str, result=bool)
    def restoreVersion(self, name):
        """Restore a version: one new change that makes the document as it was then (undoable like any other)."""
        def go():
            c = self.doc.restore_version(name, self.who)
            self._set_status(c.label if c is not None else f'Already as in version "{name}"')
        return self._guard(go)
