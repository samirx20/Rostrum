"""A pen stroke on a drawing or on any element that can hold paint (a shape, text, picture, path: its paint stays
inside its outline and moves with it): one press-drag-release = one Drag = one change (one undo step). No Qt.

Press: previews `paint.stroke` (a fixed id, the points so far, in the paint canvas's px) at the frame the playhead is
on: the operation makes the drawing, the paint layer and the paint size if missing, in the same change. Each move
previews `stroke.set {points}`; release records the one change. Canvas px come from composition px through the
layer's place at the press (`placer(layer id)`: the engine's own placement through its groups, the camera and tilt;
rostrum2d/placement.py, the one mapping agents' strokes use too). With `make` (the Add menu's layer.add calls for a drawing) the same change first
makes that drawing layer: Draw tool on, none selected, one undo step. `layer` "new": the stroke starts a new paint layer.
"""
from __future__ import annotations

from rostrum2d.drawing import frame_number
from rostrum2d.placement import canvas_points
from rostrum2d.evaluate import resolve
from rostrum_core.ids import random_id
from rostrum_gui.edits import Drag

MIN_STEP = 0.5            # canvas px: a move closer than this to the last point adds nothing


class StrokeDrag:
    def __init__(self, doc, who, layer_id: str, t: float, fps: float, brush: dict, x: float, y: float, placer, pressure=1.0,
                 make=None, layer: str = ""):
        self.doc, self.sid, self.points = doc, random_id("stroke"), []
        self._drag = Drag(doc, who, "Paint")
        try:
            if make:
                self._drag.preview(make)
            self.item = doc.item(layer_id)
            self.props = resolve(self.item, t)
            self.place = placer(layer_id)
            self._add(x, y, pressure)
            self._drag.preview([{"op": "paint.stroke", "target": [layer_id],
                                 "args": {**brush, "id": self.sid, "points": self.points, "space": "canvas", "layer": layer,
                                          "frame": max(0, frame_number(t, fps))}}])
        except Exception:
            self._drag.end(cancel=True)
            raise

    def _add(self, x, y, pressure) -> bool:
        cx, cy = canvas_points(self.item, self.props, self.place, [[x, y]])[0]
        if self.points and abs(cx - self.points[-1][0]) < MIN_STEP and abs(cy - self.points[-1][1]) < MIN_STEP:
            return False
        self.points.append([cx, cy, round(min(max(pressure, 0.0), 1.0), 3)])
        return True

    def move(self, x, y, pressure=1.0):
        if self._add(x, y, pressure):
            self._drag.preview([{"op": "stroke.set", "target": [self.sid], "args": {"points": self.points}}])

    def end(self):
        """The one change, or None if the stroke was refused."""
        return self._drag.end()

    def cancel(self):
        self._drag.end(cancel=True)
