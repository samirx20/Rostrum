"""The bridge's edit slots (a slot mix-in, see parts.py): every one an operation through doc.apply, recorded with
the person's name. A scrub goes through doc.gesture (one change for the whole drag). A refused edit fails loudly:
`_guard` reports it (console + status), never swallows it, never crashes. With several items selected, each edit is
ONE change on every one of them (one doc.apply with a call per item; one scrub moves them all).
The mix-in reaches the bridge through `self` (`self.doc`, `self.who`, `self._kit` (its state), `self._fail`,
`self._set_status`, `self._commands`, `self.select`) and the app's hooks (`edit_call`, `animate_calls`, ...).
"""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_core import RostrumError, desk

from . import commands
from .edits import Scrub, edit_label
from .parts import SlotMixin


class EditSlots(SlotMixin):
    @Slot(str, "QVariant", result=bool)
    def setValue(self, param, value):
        """One inspector edit = one change on the items it is for (quick repeats of the same field merge: the core's
        nudge). A typed value goes to the items held when its typing started (holdEdit), whatever is selected now."""
        ids = self._targets(param)
        if not ids:
            self._fail(f"Error: setValue {param}: the item(s) it was typed for are gone; {value!r} dropped.",
                       "The typed value was dropped: the item it was typed for is gone.")
            return False
        return self._guard(lambda: self._apply([self.edit_call(i, param, value) for i in ids],
                                               self._many(edit_label(self.doc, ids[0], param, value), len(ids))))

    @Slot(str)
    def holdEdit(self, param):
        """A settings field's caret went in: what it commits goes to the items selected now (pending.py)."""
        self._kit.held = (param, list(self._kit.selection))

    @Slot(str)
    def releaseEdit(self, param):
        """The field's caret left (after its commit)."""
        if self._kit.held and self._kit.held[0] == param:
            self._kit.held = None

    def _targets(self, param):
        held = self._kit.held
        ids = held[1] if held and held[0] == param else self._kit.selection
        return [i for i in ids if self.doc.has(i)]

    @Slot(str)
    def toggleAnimate(self, param):
        """The key mark's toggle on a row: the app's animate_calls, as one change. Several items: start animating
        the ones that aren't yet; when all are, stop them all."""
        def go():
            states = {i: self.anim_state(self.doc.item(i), param) for i in self._kit.selection}
            todo = [i for i, s in states.items() if s == "still"] or list(self._kit.selection)
            self._apply_each(lambda i: self.animate_calls(i, param), todo)
        self._guard(go)

    @Slot(str)
    def clearExpression(self, param):
        """The clear button on a row driven by an expression: the app's clear_expr_calls, as one change."""
        self._guard(lambda: self._apply_each(lambda i: self.clear_expr_calls(i, param), self._kit.selection))

    @Slot(str)
    def beginScrub(self, param):
        self.endScrub()
        def go():
            self._kit.scrub = Scrub(self.doc, self.who, list(self._kit.selection), param, self.edit_call)
        self._guard(go)

    @Slot(str, "QVariant")
    def scrub(self, param, value):
        if self._kit.scrub is None or self._kit.scrub.name != param:
            self.beginScrub(param)
        if self._kit.scrub is not None:
            self._guard(lambda: self._kit.scrub.preview(value))

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
        if "do" in cmd:                     # an app's own command that isn't an operation (extra_commands)
            if not callable(cmd["do"]):     # a word where a function belongs: say so, never "'str' is not callable"
                self._fail(f'Error: command bar: "{key}" has "do" = {cmd["do"]!r}; it must be a function (extra_commands).')
                return False
            return self._guard(cmd["do"])
        return self._guard(lambda: self._apply(cmd["calls"], cmd["label"]))

    @Slot()
    def undo(self):
        """The person's newest change in this document or a joined one (the markers): one history (desk.py)."""
        self._guard(lambda: self._step(desk.undo, "Nothing to undo"))

    @Slot()
    def redo(self):
        self._guard(lambda: self._step(desk.redo, "Nothing to redo"))

    def _step(self, fn, nothing):
        pairs = [(self.doc, None)] + [(p.history_doc(), p) for p in self._kit.partners]
        pairs = [(d, p) for d, p in pairs if d is not None]
        hit = fn([d for d, _ in pairs], self.who, self.open_item)
        for doc, _ in hit.all if hit is not None else ():      # a step across documents changed each of them
            partner = next((p for d, p in pairs if d is doc), None)
            if partner is not None:
                partner.stepped(doc)
        self._done(hit[1] if hit else None, nothing, said=True)

    def _apply(self, calls, label):
        self._done(self.doc.apply(calls, self.who, label=label), "")

    def _apply_each(self, calls_of, ids):
        """`calls_of(id) -> (calls, label)` for each item, applied as one change."""
        made = [calls_of(i) for i in ids]
        self._apply([c for calls, _ in made for c in calls], self._many(made[0][1]) if len(made) > 1 else made[0][1])

    def _many(self, label, n=None):
        n = len(self._kit.selection) if n is None else n
        return f"{label} on {n} items" if n > 1 else label

    def _close_scrub(self, cancel):
        s, self._kit.scrub = self._kit.scrub, None
        if s is not None:
            self._guard(lambda: self._done(s.end(cancel), ""))

    def _done(self, change, nothing, said=False):
        """A person's own change clears the message (they see it on screen; its name is on ↶ and in History);
        undo / redo show their change's own label, which the core words once ("Undid: Move title"); no change
        says `nothing`."""
        self._set_status(nothing if change is None else change.label if said else "")

    def _guard(self, fn) -> bool:
        """Run an edit; a refusal is reported (console + status), never swallowed, never a crash."""
        try:
            fn()
            return True
        except RostrumError as e:
            self._fail(e.line(), e.person())
            return False
