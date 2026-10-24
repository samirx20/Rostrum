"""Wet ink where the paint is not the layer's own: a smudge painted in place through an element smears its painting
(the drawing that element shows), laid over the element through the painted fill's one mapping (rostrum2d/painted.py)
at the tile under the press; an eraser on a painting opened on its own shows the empty canvas under it. No Qt.
"""
from __future__ import annotations

import numpy as np
from rostrum2d import drawing as D
from rostrum2d.placement import comp_point
from rostrum_paint import canvas

from .wet import reveal_rect

BARE = (16, 16, 16)             # the canvas well under an opened painting (Theme.sunken)
STRAIGHT = 1e-3                 # comp px: how far off a straight, unturned mapping may be and still take a smear


def smear(view, brush: dict, stroke, painting: dict, n: int):
    """A smudge's wet ink on the painting seen through `stroke`'s layer (strokes.StrokeDrag with a fill) at the
    painting's frame `n` (painter._n), or None when the painting is turned on the canvas (Rotation, a turned layer):
    its smear then shows when it lands."""
    m = getattr(stroke, "_map", None)
    if m is None or not stroke.points:
        return None
    pw, ph = m.pw, m.ph
    kx, ky = int(np.floor((stroke.points[0][0] + 0.5) / pw)), int(np.floor((stroke.points[0][1] + 0.5) / ph))
    ox, oy = kx * pw, ky * ph                      # the tile under the press, in the painting's unwrapped px

    def at(px, py):
        return comp_point(stroke.place, *m.to_layer(ox + px, oy + py))
    o, ax, ay = at(-0.5, -0.5), at(0.5, -0.5), at(-0.5, 0.5)
    if abs(ax[1] - o[1]) > STRAIGHT or abs(ay[0] - o[0]) > STRAIGHT:
        return None
    here = D.frame_at(painting, n) if D.each_frame(painting) else (painting["frames"] or [None])[0]
    paint = canvas.render(here, pw, ph).rgba.copy() if here else np.zeros((ph, pw, 4), np.float32)
    ink = view.ink(brush, stroke.sid, 1.0, (pw, ph), np.ascontiguousarray(paint, np.float32),
                   (o[0], o[1], ax[0] - o[0], ay[1] - o[1]))
    ink.shift = (-ox, -oy)
    return ink


def bare(visible: dict | None, x: float, y: float) -> tuple[np.ndarray, tuple[int, int]]:
    """(the reveal picture, its world top-left) for an eraser on an opened painting: the empty canvas, as far as the
    canvas shows (one colour: a view of one pixel, no memory per px)."""
    r = reveal_rect(visible, x, y)
    px = np.broadcast_to(np.array(BARE, np.uint8), (r["h"], r["w"], 3))
    return px, (r["x"], r["y"])
