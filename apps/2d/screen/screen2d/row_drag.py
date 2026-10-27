"""A layer row pulled up or down in the timeline's list (LayerRows.qml, LayerName.qml): one gesture from the press's pull
to the drop, so the drop is one undo step ("Move <layer>", the same layer.arrange an agent calls: layer_order.arrange_call)
and Esc while the button is held puts everything back with no step (drag_cancel.py finds this drag like any other).
The insert line and the row under the pointer are the list's own (QML); this holds only the gesture. backend.rowDrag.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot
from rostrum_gui.edits import Drag


class RowDrag(QObject):
    cancelled = Signal()            # Esc (or the pointer taken away): the list drops its insert line and ghost row

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b, self._drag, self._layer = bridge, None, ""

    @Slot(str, result=bool)
    def begin(self, layer_id):
        self.cancelDrag()
        b = self.b
        if not b.doc.has(layer_id):
            return False

        def go():
            self._drag, self._layer = Drag(b.doc, b.who, f"Move {b.label_of(b.doc.item(layer_id))}"), layer_id
        return b._guard(go)

    @Slot(str, str, result=bool)
    def drop(self, target_id, where):
        """Let go above / below / into the target row: one change, or nothing where it changes nothing."""
        d, self._drag = self._drag, None
        if d is None:
            return False
        call = self.b.arrange_call(self._layer, target_id, where) if target_id else None
        if call is None or not self.b._guard(lambda: d.preview([call])):      # (a refusal is said in the status line)
            self.b._guard(lambda: d.end(cancel=True))
            return False
        return self.b._guard(lambda: self.b._done(d.end(), ""))

    @Slot()
    def cancelDrag(self):
        d, self._drag = self._drag, None
        if d is not None:
            self.b._guard(lambda: d.end(cancel=True))
            self.cancelled.emit()
