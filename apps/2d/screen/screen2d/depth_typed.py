"""Set depth ▾ › Other depth… (UX_SPEC.md §3.8, "Painted backgrounds at depths"): a typed camera depth for the selected
drawings, beside Far / Middle / Near. The small popover under the bar holds one number; the drawings move back (and are
resized to cover the camera's whole move) live while it changes, the same calls as Far / Middle / Near
(action_rules `depth`: drawing.set depth + background.fit). Clicking away or Enter keeps it as ONE change, Esc takes
it back. Offered to QML as `backend.depthTyped`; screen state only.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d.fields import FIELDS
from rostrum_gui.edits import Drag

from .action_rules import RULES

DEPTH = next(p for p in FIELDS["drawing"] if p.name == "depth")      # the field's own range: one source of truth


class DepthTyped(QObject):
    changed = Signal()
    opened = Signal()               # QML opens the popover (the action's `do`)

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._drag, self._value, self._what = bridge, None, 1.0, ""

    open = Property(bool, lambda self: self._drag is not None, notify=changed)
    value = Property(float, lambda self: self._value, notify=changed)
    what = Property(str, lambda self: self._what, notify=changed)
    low = Property(float, lambda self: DEPTH.min, constant=True)
    high = Property(float, lambda self: DEPTH.max, constant=True)

    @Slot(result=bool)
    def start(self):
        """Open it on the selected drawings, at the first one's depth now."""
        self.end()
        f = self.b._facts()
        if not f.ids:
            return False
        self._value = float(f.items[0].get("depth", 0.0))
        self._what = self.b.selection_label(f.ids)
        if not self.b.guard(lambda: setattr(self, "_drag", Drag(self.b.doc, self.b.who, "Set depth"))):
            return False
        self.changed.emit()
        self.opened.emit()
        return True

    @Slot(float)
    def setValue(self, v):
        self._value = min(max(float(v), DEPTH.min), DEPTH.max)
        if self._drag is not None:
            self.b.guard(lambda: self._drag.preview(RULES["depth"](self.b._facts(), round(self._value, 3))))
        self.changed.emit()

    @Slot()
    def end(self):
        """Click away / Enter: keep it (one change; nothing if the depth did not change)."""
        d, self._drag = self._drag, None
        if d is not None:
            self.b.guard(lambda: self.b.done(d.end(), ""))
            self.changed.emit()

    @Slot()
    def cancel(self):
        """Esc: the drawings go back to where they were (nothing recorded)."""
        d, self._drag = self._drag, None
        if d is not None:
            self.b.guard(lambda: d.end(cancel=True))
            self.b._set_status("Set depth cancelled")
            self.changed.emit()
