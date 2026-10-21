"""The bridge's edit slots (a slot mix-in, see parts.py): every one an operation through doc.apply, recorded with
the person's name. A scrub goes through doc.gesture (one change for the whole drag). A refused edit fails loudly:
`_guard` reports it (console + status), never swallows it, never crashes.
The mix-in reaches the bridge through `self` (`self.doc`, `self.who`, `self._sel`, `self._scrub`, `self._fail`,
`self._set_status`, `self._commands`, `self.select`) and the app's hooks (`edit_call`, `animate_calls`, ...).
"""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_core import RostrumError

from . import commands
from .edits import Scrub, edit_label
from .parts import SlotMixin


class EditSlots(SlotMixin):
    @Slot(str, "QVariant", result=bool)
    def setValue(self, param, value):
        """One inspector edit = one change (quick repeats of the same field merge: the core's nudge)."""
        return self._guard(lambda: self._apply([self.edit_call(self._sel, param, value)],
                                               edit_label(self.doc, self._sel, param, value)))

    @Slot(str)
    def toggleAnimate(self, param):
        """The key mark's toggle on a row: the app's animate_calls, as one change."""
        self._guard(lambda: self._apply(*self.animate_calls(self._sel, param)))

    @Slot(str)
    def clearExpression(self, param):
        """The clear button on a row driven by an expression: the app's clear_expr_calls, as one change."""
        self._guard(lambda: self._apply(*self.clear_expr_calls(self._sel, param)))

    @Slot(str)
    def beginScrub(self, param):
        self.endScrub()
        def go():
            self._scrub = Scrub(self.doc, self.who, self._sel, param, self.edit_call)
        self._guard(go)

    @Slot(str, "QVariant")
    def scrub(self, param, value):
        if self._scrub is None or self._scrub.name != param:
            self.beginScrub(param)
        if self._scrub is not None:
            self._guard(lambda: self._scrub.preview(value))

    @Slot()
    def endScrub(self):
        self._close_scrub(cancel=False)

    @Slot()
    def cancelScrub(self):
        self._close_scrub(cancel=True)

    @Slot(str, result="QVariantList")
    def commands(self, query):
        return [{k: c[k] for k in ("key", "label", "hint")} for c in commands.search(self._commands(), query)]

    @Slot(str, result=bool)
    def run(self, key):
        """Run a command-bar command by key: its calls as one change (or a selection)."""
        cmd = next((c for c in self._commands() if c["key"] == key), None)
        if cmd is None:
            self._fail(f'Error: command bar: "{key}" is not available right now.')
            return False
        if "select" in cmd:
            self.select(cmd["select"])
            return True
        return self._guard(lambda: self._apply(cmd["calls"], cmd["label"]))

    @Slot()
    def undo(self):
        self._guard(lambda: self._done(self.doc.undo(self.who), "Nothing to undo"))

    @Slot()
    def redo(self):
        self._guard(lambda: self._done(self.doc.redo(self.who), "Nothing to redo"))

    def _apply(self, calls, label):
        self._done(self.doc.apply(calls, self.who, label=label), "")

    def _close_scrub(self, cancel):
        s, self._scrub = self._scrub, None
        if s is not None:
            self._guard(lambda: self._done(s.end(cancel), ""))

    def _done(self, change, nothing):
        self._set_status(change.label if change is not None else nothing)

    def _guard(self, fn) -> bool:
        """Run an edit; a refusal is reported (console + status), never swallowed, never a crash."""
        try:
            fn()
            return True
        except RostrumError as e:
            self._fail(e.line())
            return False
