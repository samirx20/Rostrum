"""Wet ink on a seamless painting (the painting kit's wrap.py), painted in place through an element: the stroke shows at
once where the pen is (wet.py) and, where it crosses the painting's edge, also on the opposite side, as it will land.
`copies` are those other places as moves of the wet picture in composition px; the screen shows them inside the
element's box. No Qt.
"""
from __future__ import annotations

import math

from rostrum2d import paintings
from rostrum2d.placement import comp_point

PAD = 2.0                       # painting px past the brush's radius (its soft edge)
SIDES = [(kx, ky) for kx in (-1, 0, 1) for ky in (-1, 0, 1) if (kx, ky) != (0, 0)]


def copies(stroke, painting: dict | None, size: float) -> list[dict]:
    """[{x, y}]: where else the wet picture of `stroke` (strokes.StrokeDrag painting through an element, its points in
    the painting's px) shows: one move per side it crosses. None for a painting that isn't seamless."""
    m = getattr(stroke, "_map", None)
    if m is None or painting is None or not paintings.seamless(painting) or not stroke.points:
        return []
    pts, r = stroke.points, size / 2 + PAD
    kx0, ky0 = math.floor((pts[0][0] + 0.5) / m.pw), math.floor((pts[0][1] + 0.5) / m.ph)
    x0, x1 = min(q[0] for q in pts) - kx0 * m.pw - r, max(q[0] for q in pts) - kx0 * m.pw + r
    y0, y1 = min(q[1] for q in pts) - ky0 * m.ph - r, max(q[1] for q in pts) - ky0 * m.ph + r
    px, py = pts[0][0], pts[0][1]
    here = comp_point(stroke.place, *m.to_layer(px, py))
    out = []
    for kx, ky in SIDES:
        dx, dy = kx * m.pw, ky * m.ph
        if x0 + dx < m.pw and x1 + dx > 0 and y0 + dy < m.ph and y1 + dy > 0:
            there = comp_point(stroke.place, *m.to_layer(px + dx, py + dy))
            out.append({"x": there[0] - here[0], "y": there[1] - here[1]})
    return out
