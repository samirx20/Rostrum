"""The amounts popover's one live session (amounts.py builds its rows): what the kit's AmountsPopover.qml reads, in the
shape InspectorRow talks to (rows, moreOpen, setValue, beginScrub / scrub / endScrub …), so the popover's rows are the
settings panel's own rows.

Changes land once per frame (a slider drag's many moves: the action re-runs for the last value, after the frame the
pointer's own move drew). Opening starts ONE gesture (edits.Drag): the action runs at once with the amounts shown, and every change runs it
again on the ORIGINAL items (a fresh preview: Humanise twice never loosens twice). `keep()` (Enter, a click away)
ends it as ONE change named with the amounts ("Humanise · 12 notes · 15 ms, 8 %"); `cancel()` (Esc) puts everything
back and records nothing. The amounts kept are remembered per action for this window (screen state, never saved):
the action's button and key run with them next time. The hub (action_hub.py) opens it; the app gives `drag_fn(label)`
(its document's Drag), `kept_fn(change, label)` (its message line and selection) and `say_fn(line)`.
"""
from __future__ import annotations

import random

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core import RostrumError

from . import amounts as A
from . import rows as R
from .after_frame import AfterFrame
from .model import RowsModel


class AmountsPage(QObject):
    changed = Signal()

    def __init__(self, drag_fn, kept_fn, say_fn, parent=None):
        super().__init__(parent)
        self._drag_fn, self._kept_fn, self._say = drag_fn, kept_fn, say_fn
        self.model = RowsModel(R.ROLES, self)
        self.memory: dict[str, dict] = {}       # action id -> the amounts last kept
        self._action = self._facts = self._drag = None
        self._title, self._more, self._rows, self._vals, self._found = "", False, [], {}, []
        self._static: list[dict] = []
        self._later = AfterFrame(self._refresh, self)     # a slider drag's moves: one re-run per frame, the last value

    # ---- what the popover (and InspectorRow) reads -------------------------------------------------------------
    @Property(QObject, constant=True)
    def rows(self):
        return self.model

    @Property(str, notify=changed)
    def title(self):
        return self._title

    @Property(bool, notify=changed)
    def moreOpen(self):
        return self._more

    @Property(bool, notify=changed)
    def again(self):
        """An "Another take" button: one of the amounts is a seed."""
        return A.AGAIN in self._vals

    @Property(bool, notify=changed)
    def live(self):
        return self._drag is not None

    @Property("QVariantMap", notify=changed)
    def selectedItem(self):
        return {"id": "amounts", "label": self._title, "kind": ""}

    def label(self) -> str:
        """What the history and the message line call the change now: "Repeat · bar 5–6 · 4 times"."""
        said = A.words(self._rows)
        return f"{self._title} · {said}" if said else self._title

    # ---- the session -------------------------------------------------------------------------------------------
    def open(self, action, facts, title):
        """Start a session for `action` on the selection `facts`: its rows, then the action at once, live."""
        self.cancel()
        mine = self.memory.get(action.id, {})
        calls = action.calls(facts, mine)
        fit = action.fit(facts, mine) if action.fit else {}
        self._found = A.params(action, calls, facts.doc.kind.registry, fit)
        self._action, self._facts, self._title, self._more = action, facts, title, False
        self._static = A.layout(self._found)
        self._vals = A.values(self._found, mine, fit)
        self._drag = self._drag_fn(title)
        self._refresh(preview=False, instant=True)   # at once, on the delegates made before (RowsModel keeps them per
        self._later.ask()                            # setting, parked between uses); the action runs the frame after

    @Slot()
    def keep(self):
        """Enter or a click away: the session is ONE change, named with its amounts."""
        self._later.flush()                    # a change still waiting for its frame lands first
        d, self._drag = self._drag, None
        if d is None:
            return
        label = self.label()
        self.memory[self._action.id] = dict(self._vals)
        self.changed.emit()
        self._kept_fn(d.end(label=label), label)

    @Slot()
    def cancel(self):
        """Esc: everything back as it was before the popover opened; nothing recorded."""
        self._later.cancel()
        d, self._drag = self._drag, None
        if d is not None:
            d.end(cancel=True)
            self.changed.emit()

    @Slot()
    def anotherTake(self):
        """The same amounts, another result: a new seed."""
        old = self._vals.get(A.AGAIN)
        self._vals[A.AGAIN] = next(s for s in iter(lambda: random.randint(1, 999999), None) if s != old)
        self._refresh()

    # ---- InspectorRow's calls ----------------------------------------------------------------------------------
    @Slot(str, "QVariant")
    def setValue(self, name, value):
        p = next((p for p in self._found if p.name == name), None)
        if p is not None and p.type == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            value = int(round(value)) if p.integer else round(float(value), 6)
        if self._drag is None or self._vals.get(name) == value:
            return
        self._vals[name] = value
        self._later.ask()

    @Slot(str)
    def beginScrub(self, name):
        pass                                   # the whole popover is one gesture already

    @Slot(str, "QVariant")
    def scrub(self, name, value):
        self.setValue(name, value)

    @Slot()
    def endScrub(self):
        pass

    @Slot()
    def cancelScrub(self):
        pass

    @Slot()
    def toggleMore(self):
        self._more = not self._more
        self._refresh(preview=False)

    @Slot(str)
    def toggleAnimate(self, _name):           # amounts have no keys, groups, expressions, files or row buttons
        pass

    @Slot(str)
    def toggleGroup(self, _name):
        pass

    @Slot(str)
    def clearExpression(self, _name):
        pass

    @Slot(str)
    def rowAction(self, _id):
        pass

    # ---- inside ------------------------------------------------------------------------------------------------
    def _refresh(self, preview=True, instant=False):
        a, f = self._action, self._facts
        fit = a.fit(f, self._vals) if a.fit else {}
        self._rows = A.evaluate(self._static, self._vals, fit, self._more)
        self.model.update(self._rows, instant)
        self.changed.emit()
        if preview and self._drag is not None:
            now = A.shown(self._rows)
            try:
                self._drag.preview(lambda: a.calls(f, now), fresh=True)
                self._say(self.label())
            except RostrumError as e:           # this amount can't be done (past the 128 notes): said, last good kept
                self._say(e.person())
