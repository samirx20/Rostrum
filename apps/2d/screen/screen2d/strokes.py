"""A pen stroke on a drawing layer: one press-drag-release = one Drag = one change (one undo step). No Qt.

Press: previews `stroke.add` (a fixed id, the points so far) on the paint layer of the frame the drawing shows at
the playhead; if it shows none, the same change first adds the frame (`frame.add at=<current frame>`), and a paint
layer if the new frame has none. Each move previews `stroke.set {points}`; release records the one change.
Canvas px of the drawing come from composition px (rostrum2d.drawing.to_canvas: the layer's x, y, anchor, scale and
rotation; a drawing inside a group is not placed from the group's corner yet). With `make` (the Add menu's layer.add
calls for a drawing) the same change first makes that drawing layer: Draw tool on, none selected, one undo step.
"""
from __future__ import annotations

from rostrum2d.drawing import frame_at, frame_number, to_canvas
from rostrum2d.evaluate import resolve
from rostrum_core import RostrumError, codes
from rostrum_core.ids import random_id
from rostrum_gui.edits import Drag

MIN_STEP = 0.5            # canvas px: a move closer than this to the last point adds nothing


def paint_target(frame: dict) -> dict | None:
    """The paint layer strokes go to: the topmost one that is not locked."""
    return next((p for p in reversed(frame.get("paints", [])) if not p.get("locked")), None)


class StrokeDrag:
    def __init__(self, doc, who, layer_id: str, t: float, fps: float, brush: dict, x: float, y: float, pressure=1.0, make=None):
        self.doc, self.sid, self.points = doc, random_id("stroke"), []
        self._drag = Drag(doc, who, "Draw")
        try:
            if make:
                self._drag.preview(make)
            self.props = resolve(doc.item(layer_id), t)
            n = frame_number(t, fps)
            frame = frame_at(doc.item(layer_id), n)
            if frame is None:
                fid = random_id("frame")
                self._drag.preview([{"op": "frame.add", "target": [layer_id], "args": {"id": fid, "at": n}}])
                frame = doc.item(fid)
            paint = paint_target(frame)
            if paint is None and frame.get("paints"):
                raise RostrumError(codes.CONFLICT, "draw", f'"{frame["id"]}"', "every paint layer of this drawing is locked")
            if paint is None:
                pid = random_id("paint")
                self._drag.preview([{"op": "paint.add", "target": [frame["id"]], "args": {"id": pid}}])
                paint = doc.item(pid)
            self._add(x, y, pressure)
            self._drag.preview([{"op": "stroke.add", "target": [paint["id"]],
                                 "args": {**brush, "id": self.sid, "points": self.points}}])
        except Exception:
            self._drag.end(cancel=True)
            raise

    def _add(self, x, y, pressure) -> bool:
        cx, cy = to_canvas(self.props, x, y)
        if self.points and abs(cx - self.points[-1][0]) < MIN_STEP and abs(cy - self.points[-1][1]) < MIN_STEP:
            return False
        self.points.append([round(cx, 2), round(cy, 2), round(min(max(pressure, 0.0), 1.0), 3)])
        return True

    def move(self, x, y, pressure=1.0):
        if self._add(x, y, pressure):
            self._drag.preview([{"op": "stroke.set", "target": [self.sid], "args": {"points": self.points}}])

    def end(self):
        """The one change, or None if the stroke was refused."""
        return self._drag.end()

    def cancel(self):
        self._drag.end(cancel=True)
