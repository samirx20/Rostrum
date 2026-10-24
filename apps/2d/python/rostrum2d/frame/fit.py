"""Where the frame must go to show a rectangle of the world or some layers (frame.fit, frame.cut with `to`; the
maths of FRAME.md › Framing). Pure: values in, (x, y, zoom) out, the export formula of view.py:

    out(p) = O + R(−roll) · zˢ · (p − H − s · (F − H)),   s = 1 / (1 + depth)

A rectangle: the largest output-shaped box, turned by roll, inside it. Layers: the frame that shows every given
point (each with its layer's depth) inside the output less `pad` on each side, as close as that allows, centred."""
from __future__ import annotations

import math

ZOOM = (0.01, 100.0)        # the frame's zoom field range (frame/fields.py)


def rect(r: tuple, size: tuple, roll: float, pad: float) -> tuple[float, float, float]:
    """(x, y, zoom) for the largest frame turned by `roll` whose inside less `pad` lies in the world rectangle
    r = (x, y, w, h): its box seen in the world is W/z × H/z, so its turned outline is (cW + sH, sW + cH) / z."""
    x, y, w, h = r
    W, H = size
    c, s = abs(math.cos(math.radians(roll))), abs(math.sin(math.radians(roll)))
    z = max((c * W + s * H) / w, (s * W + c * H) / h) * (1 - 2 * pad)
    return x + w / 2, y + h / 2, z


def _turn(x: float, y: float, deg: float) -> tuple[float, float]:
    r = math.radians(deg)
    return math.cos(r) * x - math.sin(r) * y, math.sin(r) * x + math.cos(r) * y


def points(groups: list, size: tuple, home: tuple, roll: float, pad: float) -> tuple[float, float, float] | None:
    """(x, y, zoom) that shows every point inside the output less `pad`; None when even the smallest zoom can't.
    `groups`: [(depth, [(x, y) world px …]) …]. With u = R(−roll) · F and c = R(−roll) · (p − (1 − s) · H), a point
    shows at O + zˢ · (c − s · u), so for one zoom each axis is a range of u; the widest zoom is found by halving
    (a bigger zoom only narrows every range)."""
    W, H = size
    half = (W / 2 - pad * W, H / 2 - pad * H)
    rows = [(1 / (1 + d), _turn(px - (1 - 1 / (1 + d)) * home[0], py - (1 - 1 / (1 + d)) * home[1], -roll))
            for d, pts in groups for px, py in pts]

    def ranges(z):
        out = []
        for axis in (0, 1):
            lo = max((c[axis] - half[axis] / z ** s) / s for s, c in rows)
            hi = min((c[axis] + half[axis] / z ** s) / s for s, c in rows)
            out.append((lo, hi))
        return out

    fits = lambda z: all(lo <= hi for lo, hi in ranges(z))  # noqa: E731
    lo, hi = ZOOM
    if not fits(lo):
        return None
    if fits(hi):
        lo = hi
    else:
        for _ in range(60):                     # halving in log steps: far below a thousandth of a zoom step
            mid = math.sqrt(lo * hi)
            lo, hi = (mid, hi) if fits(mid) else (lo, mid)
    (ax, bx), (ay, by) = ranges(lo)
    fx, fy = _turn((ax + bx) / 2, (ay + by) / 2, roll)
    return fx, fy, lo
