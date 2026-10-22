"""The picked strokes' handles while Draw is on (UX_SPEC.md §3.8, "Select and move paint"): drag a corner of their box to
scale them about its centre, drag the knob above it to turn them (Shift: in 15° steps). Press-drag-release is one
gesture = one undo step (the pen routes the press here when `handleAt` names a handle: Stage.qml), each move previewing `stroke.set {points, size}` (fills: their outline) from where the
strokes were at the press, so nothing compounds. The handles' places are the box's (QML draws them from `box`).

A slot mix-in for StrokeSelect (stroke_select.py: the selection, the mapping, `_begin_drag`, `_set_calls`).
"""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_gui.parts import SlotMixin

from . import stroke_geom as G

LABELS = {"scale": "Scale strokes", "turn": "Turn strokes"}


class StrokeHandles(SlotMixin):
    _handle = None              # (kind, centre, press) while a handle is dragged

    @Slot(float, float, float, result=str)
    def handleAt(self, x, y, zoom):
        """The handle under (x, y) composition px at this zoom: "scale", "turn" or "" (the pen's press asks first)."""
        return G.handle_hit(self.box, x, y, zoom) if self._ids else ""

    @Slot(str, float, float, result=bool)
    def beginHandle(self, kind, x, y):
        """A press on a handle ("scale": a corner, "turn": the knob) at (x, y) composition px."""
        b = self.box
        if kind not in LABELS or not b or self._drag is not None:
            return False
        centre = (b["x"] + b["w"] / 2, b["y"] + b["h"] / 2)

        def go():
            self._place = self.b.place_of(self._layer)
            self._begin_drag(LABELS[kind])
        if not self.b.guard(go):
            return False
        self._handle = (kind, centre, (x, y))
        return True

    @Slot(float, float, bool)
    def handleTo(self, x, y, steps=False):
        """The pointer is at (x, y): the strokes scaled or turned by how far it went round or out from the centre."""
        if self._drag is None or self._handle is None:
            return
        kind, centre, press = self._handle
        scale, turn = G.handle_amount(kind, centre, press, (x, y), steps)

        def go():
            self._comp = {i: G.transformed(p, centre, scale, turn) for i, p in self._start.items()}
            self._drag.preview(self._set_calls(lambda p: (p, scale if scale != 1 else 0)))
        self.b.guard(go)
        self.changed.emit()

    @Slot()
    def endHandle(self):
        self._handle = None
        self.endMove()

    def drag_handle(self, kind: str, to: tuple[float, float], steps: bool = False) -> bool:
        """A whole handle drag from its place to `to` (composition px), as one change (steps, agents' screens)."""
        b = self.box
        if not b:
            return False
        at = G.handle_point(kind, b)
        if not self.beginHandle(kind, *at):
            return False
        self.handleTo(*to, steps)
        self.endHandle()
        return True
