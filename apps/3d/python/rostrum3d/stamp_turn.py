"""A stamp's turn (paint.stamp): Turn 0 is upright, measured from a stable direction, not from the laid-flat paint
picture (which lies at any angle on the surface). A stamp stroke keeps what was asked (`stampTurn`, paint_fields.STROKE)
and its kit `angle` is worked out each time it is laid, where it lands on the canvas as it is then:

- from the view (`viewPoints`): up = the screen's up there (paint_view.lay, from the texel picture's steps);
- on a clay (`anchors`): up = the clay's own +Y laid on the surface (its tangent plane), its −Z where the surface faces
  straight up or down; through that triangle's own unfolding, so a seam next to the spot never turns it
  (`upright_on_clay`, before clay_paint lays the strokes).

So a clay reshaped and unfolded anew, or an item moved under a view stamp, keeps the stamp upright. The kit's dab
turns its picture's columns along (cos a, sin a) in canvas px (y down): its up is (sin a, −cos a); `angle_of` gives
the `a` whose up is a canvas direction. Turn is clockwise as seen (with the surface's picture not mirrored).
"""
from __future__ import annotations

import math

import numpy as np

STEEP = 0.9                         # |normal · Y| above this: the surface faces up or down, up is −Z there


def angle_of(up_px, turn: float) -> float:
    """The kit angle (degrees) that stands the picture along canvas direction `up_px` (x right, y down), turned by
    `turn` degrees clockwise."""
    dx, dy = float(up_px[0]), float(up_px[1])
    if not (math.isfinite(dx) and math.isfinite(dy)) or dx * dx + dy * dy < 1e-18:
        return round(float(turn), 4)                     # nothing to measure by: the paint picture's up
    return round((math.degrees(math.atan2(dx, -dy)) + float(turn) + 180.0) % 360.0 - 180.0, 4)


def surface_up(normal) -> np.ndarray:
    """The clay's +Y on the tangent plane of `normal` (−Z where the surface faces up or down), unit."""
    n = np.asarray(normal, np.float64)
    n = n / max(np.linalg.norm(n), 1e-12)
    up = np.array([0.0, 0.0, -1.0]) if abs(n[1]) > STEEP else np.array([0.0, 1.0, 0.0])
    t = up - (up @ n) * n
    return t / max(np.linalg.norm(t), 1e-12)


def clay_angle(surface, anchor, turn: float) -> float:
    """The kit angle of a clay stamp at `anchor` [x, y, z, nx, ny, nz, …] on `surface` (clay_paint.Surface)."""
    p, n = np.asarray([anchor[:3]], np.float64), np.asarray([anchor[3:6]], np.float64)
    tri, bary = surface.nearest(surface.along_normal(p, n), n)
    on = surface.canvas_px(tri, bary)[0]
    step = surface.edge * 0.5
    there = surface.canvas_px(tri, surface.at(tri, p + step * surface_up(n[0])))[0]   # in that triangle's own plane
    return angle_of(there - on, turn)


def upright_on_clay(canvas: dict, surface) -> dict:
    """`canvas` (a clay) with each anchored stamp's `angle` worked out on `surface`; untouched when it has none."""
    if not any(s.get("stampTurn") is not None and s.get("anchors")
               for p in canvas.get("paints", []) for s in p.get("strokes", [])):
        return canvas
    paints = [{**p, "strokes": [{**s, "angle": clay_angle(surface, s["anchors"][0], s["stampTurn"])}
                                if s.get("stampTurn") is not None and s.get("anchors") else s
                                for s in p.get("strokes", [])]} for p in canvas.get("paints", [])]
    return {**canvas, "paints": paints}
