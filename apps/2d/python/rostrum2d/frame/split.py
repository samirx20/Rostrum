"""A curve ease cut to part of its stretch, exactly: the cubic-bezier between two keys (a named curve or `custom`,
rostrum_core.keys.easing) read from time fraction u0 to u1 is itself a cubic-bezier, found by de Casteljau's split.
The conversion of older cameras (shots.py) uses it where a cut falls inside a move."""
from __future__ import annotations

from rostrum_core.keys.easing import BEZIERS


def curve_of(key: dict) -> tuple | None:
    """A key's ease as its four bezier numbers, or None (linear, hold, spring, bounce: not a bezier)."""
    name = key.get("ease", "smooth")
    if name == "custom":
        return key.get("x1", 0.25), key.get("y1", 0.1), key.get("x2", 0.25), key.get("y2", 1.0)
    return BEZIERS.get(name)


def _lerp(a, b, s):
    return a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s


def _cut(pts, s):
    """De Casteljau at s: (the first part's points, the second part's)."""
    p0, p1, p2, p3 = pts
    a, b, c = _lerp(p0, p1, s), _lerp(p1, p2, s), _lerp(p2, p3, s)
    d, e = _lerp(a, b, s), _lerp(b, c, s)
    f = _lerp(d, e, s)
    return (p0, a, d, f), (f, e, c, p3)


def _at_x(pts, x):
    """The curve parameter where its time is x (time rises along the curve: x1, x2 in 0..1)."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if _cut(pts, mid)[0][3][0] < x:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def sub(curve: tuple, u0: float, u1: float) -> tuple[tuple, float, float] | None:
    """The part of `curve` from time fraction u0 to u1: (its four numbers, progress at u0, progress at u1), or None
    when the value hardly moves there (then a straight line is the same)."""
    x1, y1, x2, y2 = curve
    pts = ((0.0, 0.0), (x1, y1), (x2, y2), (1.0, 1.0))
    if u1 < 1:
        pts = _cut(pts, _at_x(pts, u1))[0]
    if u0 > 0:
        pts = _cut(pts, _at_x(pts, u0))[1]
    (ax, ay), (bx, by), (cx, cy), (dx, dy) = pts
    if abs(dy - ay) < 1e-9 or dx - ax < 1e-12:
        return None
    nx = lambda v: (v - ax) / (dx - ax)  # noqa: E731
    ny = lambda v: (v - ay) / (dy - ay)  # noqa: E731
    return (nx(bx), ny(by), nx(cx), ny(cy)), ay, dy
