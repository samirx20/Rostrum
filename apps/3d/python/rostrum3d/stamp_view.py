"""A stamp clicked in a view (paint.stamp `viewPoint`) on a clay, laid as a decal like one placed by `at`
(stamp_decal.py): a dab on a clay's many small flat pieces would break up. Each time the paint is laid, the click is
found on the clay through its view's texel picture (the canvas spot under it, then the triangle of the clay's unfolded
surface holding that spot), and the stamp becomes an anchored one there: its point and the triangle's direction, its
reach from its size in screen px (metres per screen px there), its up = the screen's up on the surface (`stampUp`),
both from the pixels round the click found on the clay the same way. So a
moved or reshaped clay re-lands it where the camera now sees it, upright as the screen was.
"""
from __future__ import annotations

import numpy as np

from . import paint_view

STEP = 2.0                        # screen px round the click its up and size are measured over


def _holding(surface, xy) -> tuple[int, np.ndarray] | None:
    """(triangle, barycentric) of the surface's unfolding holding canvas px `xy`, or None."""
    if getattr(surface, "_uvcentres", None) is None:
        from scipy.spatial import cKDTree
        surface._uvcentres = cKDTree(surface.uv.mean(axis=1))
    q = np.array([xy[0] / surface.size, 1.0 - xy[1] / surface.size])
    _, cand = surface._uvcentres.query(q, min(16, len(surface.tris)))
    for t in np.atleast_1d(cand):
        a, b, c = surface.uv[t]
        m = np.array([b - a, c - a]).T
        if abs(np.linalg.det(m)) < 1e-20:
            continue
        w1, w2 = np.linalg.solve(m, q - a)
        if min(w1, w2, 1 - w1 - w2) >= -1e-6:
            return int(t), np.array([1 - w1 - w2, w1, w2])
    return None


def on_surface(stroke: dict, pic, item_id: str, surface) -> dict | None:
    """The view stamp `stroke` as an anchored stamp on `surface` (None: the camera doesn't see the click on the clay).
    The click and the pixels STEP round it are each found on the clay (a clay's pieces are too small for the canvas
    to say which way is up or how big a screen px is there): up = from the pixel below to the one above, metres per
    screen px from them and the pixels left and right."""
    idx = paint_view._index(pic, item_id)
    if idx < 0:
        return None
    x, y = stroke["viewPoints"][0][:2]
    k = STEP
    s = np.array([[x, y, 1.0], [x + k, y, 1.0], [x - k, y, 1.0], [x, y - k, 1.0], [x, y + k, 1.0]])
    spot, hit, _, _ = paint_view._look(pic, idx, surface.size, s)
    found = [(_holding(surface, spot[i]) if hit[i] else None) for i in range(5)]
    if found[0] is None:
        return None
    pts = [None if f is None else f[1] @ surface.points[surface.tris[f[0]]] for f in found]
    p, n = pts[0], surface.facing[found[0][0]]
    up = (pts[3] - pts[4]) if pts[3] is not None and pts[4] is not None else None
    steps = [np.linalg.norm(pts[i] - pts[j]) / (2 * k) for i, j in ((1, 2), (3, 4))
             if pts[i] is not None and pts[j] is not None]
    mps = float(np.sqrt(np.prod(steps))) if len(steps) == 2 else steps[0] if steps else float(surface.mpp[found[0][0]])
    base = {k: v for k, v in stroke.items() if not k.startswith("view")}
    return {**base, "anchors": [[*p.tolist(), *n.tolist(), 1.0]], "reach": float(stroke["size"]) / 2 * mps,
            **({"stampUp": up.tolist()} if up is not None else {})}
