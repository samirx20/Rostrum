"""A pen stroke on a drawing or on any element that can hold paint (a shape, text, picture, path: its paint stays
inside its outline and moves with it): one press-drag-release = one Drag = one change (one undo step). No Qt.

Press: previews `paint.stroke` (a fixed id, the points so far, in the paint canvas's px) at the frame the playhead is
on: the operation makes the drawing, the paint layer and the paint size if missing, in the same change. Each move
previews `stroke.set {points}`; release records the one change. Canvas px come from composition px through the
layer's place at the press (`placer(layer id)`: the engine's own placement through its groups, the camera and tilt;
rostrum2d/placement.py, the one mapping agents' strokes use too). A pen's lean (pen_tilt.py, screen directions) goes
through the same placement, so on a turned layer it still points the way the pen leans on screen. With `make` (the Add menu's layer.add calls for a drawing) the same change first
makes that drawing layer: Draw tool on, none selected, one undo step. `layer` "new": the stroke starts a new paint layer.
"""
from __future__ import annotations

import math

from rostrum2d.drawing import frame_number
from rostrum2d.placement import canvas_points
from rostrum2d.evaluate import resolve
from rostrum2d.names import display_name
from rostrum_core.errors import RostrumError, codes
from rostrum_core.ids import random_id
from rostrum_gui.edits import Drag

MIN_STEP = 0.5            # canvas px: a move closer than this to the last point adds nothing
LEAN_STEP = 100.0         # composition px: the lean's direction is measured over this far (the canvas rounds to 0.01)


def check_showing(item: dict, own_t: float, playhead: float) -> None:
    """Paint only where the layer can be seen, as Procreate refuses a hidden layer: a stroke on a layer that is hidden, or
    has no opacity at the playhead, would be drawn and never seen. Refused loudly, naming the layer and the moment."""
    if item.get("hidden") or resolve(item, own_t).get("opacity", 1) <= 0:
        name = display_name(item)
        raise RostrumError(codes.CHECK_FAILED, "paint", f'"{name}"', f"is not showing at {playhead:.1f} s",
                           hint="Show it, or move the playhead to where it shows, then paint.",
                           plain=f"{name} isn't showing at {playhead:.1f} s. Show it or move the playhead, then paint.")


class StrokeDrag:
    def __init__(self, doc, who, layer_id: str, t: float, fps: float, brush: dict, x: float, y: float, placer, pressure=1.0,
                 make=None, layer: str = "", lean=None):
        self.doc, self.sid, self.points = doc, random_id("stroke"), []
        self._drag = Drag(doc, who, "Paint")
        try:
            if make:
                self._drag.preview(make)
            self.item = doc.item(layer_id)
            self.props = resolve(self.item, t)
            self.place = placer(layer_id)
            self._add(x, y, pressure, lean)
            self._drag.preview([{"op": "paint.stroke", "target": [layer_id],
                                 "args": {**brush, "id": self.sid, "points": self.points, "space": "canvas", "layer": layer,
                                          "frame": max(0, frame_number(t, fps))}}])
        except Exception:
            self._drag.end(cancel=True)
            raise

    def _add(self, x, y, pressure, lean=None) -> bool:
        cx, cy = canvas_points(self.item, self.props, self.place, [[x, y]])[0]
        if self.points and abs(cx - self.points[-1][0]) < MIN_STEP and abs(cy - self.points[-1][1]) < MIN_STEP:
            return False
        self.points.append([cx, cy, round(min(max(pressure, 0.0), 1.0), 3), *self._lean(x, y, lean)])
        return True

    def _lean(self, x, y, lean) -> list[float]:
        """The pen's lean (screen degrees each way) turned into the canvas' directions, the same amount of lean."""
        if not lean:
            return []
        tx, ty = lean
        amount = math.hypot(tx, ty)
        if amount == 0:
            return [0.0, 0.0]
        a, b = canvas_points(self.item, self.props, self.place,
                             [[x, y], [x + LEAN_STEP * tx / amount, y + LEAN_STEP * ty / amount]])
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy) or 1.0
        return [round(amount * dx / d, 2), round(amount * dy / d, 2)]

    def move(self, x, y, pressure=1.0, lean=None):
        if self._add(x, y, pressure, lean):
            self._drag.preview([{"op": "stroke.set", "target": [self.sid], "args": {"points": self.points}}])

    def end(self):
        """The one change, or None if the stroke was refused."""
        return self._drag.end()

    def cancel(self):
        self._drag.end(cancel=True)
