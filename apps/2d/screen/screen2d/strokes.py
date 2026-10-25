"""A pen stroke on a drawing or on any element that can hold paint (a shape, text, picture, path: its paint stays
inside its outline and moves with it): one press-drag-release = one Drag = one change (one undo step). No Qt.

Press: previews `paint.stroke` (a fixed id, the points so far, in the paint canvas's px) at the frame the playhead is
on: the operation makes the drawing, the paint layer and the paint size if missing, in the same change. Each move
previews `stroke.set {points}`; release records the one change. With `wet` (wet.py shows the stroke meanwhile) only release
writes it: the whole stroke in one call, one plain change (no drag is held open, so the document and everything that
follows it change once, not for a preview and again for the change), unless the press made a layer (`make`). Canvas px come from composition px through the
layer's place at the press (`placer(layer id)`: the engine's own placement through its groups, the camera and tilt;
rostrum2d/placement.py, the one mapping agents' strokes use too). A pen's lean (pen_tilt.py, screen directions) goes
through the same placement, so on a turned layer it still points the way the pen leans on screen. With `make` (the Add menu's layer.add calls for a drawing) the same change first
makes that drawing layer: Draw tool on, none selected, one undo step. `layer` "new": the stroke starts a new paint layer.
With `fill` (a painting the layer is filled with: painting in place) the points go on through the layer's own px into the
painting's (paint_through.mapping, the engine's layout) and the stroke goes into the painting, `through` the layer.
"""
from __future__ import annotations

import math

from rostrum2d.drawing import frame_number
from rostrum2d import paint_through
from rostrum2d.placement import canvas_points, own_point
from rostrum2d.evaluate import resolve
from rostrum2d.names import display_name
from rostrum_core.errors import RostrumError, codes
from rostrum_core.ids import random_id
from rostrum_gui.edits import Drag

MIN_STEP = 0.5            # canvas px: a move closer than this to the last point adds nothing
LEAN_STEP = 100.0         # composition px: the lean's direction is measured over this far (the canvas rounds to 0.01)


def check_showing(item: dict, own_t: float, playhead: float) -> None:
    """Paint only where the layer can be seen, as Procreate refuses a hidden layer: a stroke on a layer that is hidden, has no
    opacity at the playhead, or is outside its own start and end there, would be drawn and never seen (outside its time the
    engine has no place for it to land). Refused loudly, naming the layer and the moment it shows."""
    name = display_name(item)
    start, end = item.get("start", 0.0), item.get("end", math.inf)
    if not start - 1e-9 <= own_t < end:
        goes = f"shows from {start + playhead - own_t:.2f} s" if own_t < start else "is over by then"
        raise RostrumError(codes.CHECK_FAILED, "paint", f'"{name}"', f"is not on screen at {playhead:.2f} s",
                           hint="Move the playhead to where it shows, then paint.",
                           plain=f"{name} {goes}: move the playhead there")
    if item.get("hidden") or resolve(item, own_t).get("opacity", 1) <= 0:
        raise RostrumError(codes.CHECK_FAILED, "paint", f'"{name}"', f"is not showing at {playhead:.1f} s",
                           hint="Show it, or move the playhead to where it shows, then paint.",
                           plain=f"{name} isn't showing at {playhead:.1f} s. Show it or move the playhead, then paint.")


class StrokeDrag:
    def __init__(self, doc, who, layer_id: str, t: float, fps: float, brush: dict, x: float, y: float, placer, pressure=1.0,
                 make=None, layer: str = "", lean=None, wet: bool = False, fill: dict | None = None):
        self.doc, self.who, self.sid, self.points, self._waiting, self.wet = doc, who, random_id("stroke"), [], False, wet
        self._drag = Drag(doc, who, "Paint") if make or not wet else None
        try:
            if make:
                self._drag.preview(make)
            self.item = doc.item(layer_id)
            self.props = resolve(self.item, t)
            self.place = placer(layer_id)
            self._map = None if fill is None else paint_through.mapping(self.item, self.props, fill, t,
                                                                         (self.place["w"], self.place["h"]))
            self._add(x, y, pressure, lean)
            self._call = {"op": "paint.stroke", "target": [fill["id"] if fill else layer_id],
                          "args": {**brush, "id": self.sid, "points": self.points, "space": "canvas", "layer": layer,
                                   "frame": max(0, frame_number(t, fps)), **({"through": layer_id} if fill else {})}}
            if not wet:                 # wet: the document gets the stroke once, at the end (wet.py shows it till then)
                self._drag.preview([self._call])
        except Exception:
            self.cancel()
            raise

    def _canvas(self, points) -> list[list[float]]:
        """Composition px -> the canvas the stroke goes on: the layer's paint, or through it into its painting."""
        if self._map is None:
            return canvas_points(self.item, self.props, self.place, points)
        return self._map.points([[*own_point(self.place, q[0], q[1]), *q[2:]] for q in points])

    def _add(self, x, y, pressure, lean=None) -> bool:
        cx, cy = self._canvas([[x, y]])[0]
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
        a, b = self._canvas([[x, y], [x + LEAN_STEP * tx / amount, y + LEAN_STEP * ty / amount]])
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy) or 1.0
        return [round(amount * dx / d, 2), round(amount * dy / d, 2)]

    def move(self, x, y, pressure=1.0, lean=None) -> bool:
        """Adds the point; True if the picture needs `show()`. Cheap: the screen calls `show()` once for all the
        moves that piled up while the last picture was made, so the ink never falls behind the pen."""
        self._waiting |= self._add(x, y, pressure, lean)
        return self._waiting

    def scale(self, x: float, y: float) -> float:
        """Canvas px per composition px here (the brush size is in canvas px)."""
        a, b = self._canvas([[x, y], [x + LEAN_STEP, y]])
        return math.hypot(b[0] - a[0], b[1] - a[1]) / LEAN_STEP

    def show(self):
        if self.wet:
            return
        if self._waiting:
            self._waiting = False
            self._drag.preview([{"op": "stroke.set", "target": [self.sid], "args": {"points": self.points}}])

    def end(self):
        """The one change, or None if the stroke was refused."""
        if self._drag is None:
            return self.doc.apply([self._call], self.who, label="Paint")
        if self.wet:
            return self._drag.end(calls=[self._call])
        try:
            self.show()
        except BaseException:
            self.cancel()
            raise
        return self._drag.end()

    def cancel(self):
        if self._drag is not None:
            self._drag.end(cancel=True)
