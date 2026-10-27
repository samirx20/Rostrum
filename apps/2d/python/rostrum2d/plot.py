"""Equations, graphs and charts as path data: the few helpers a script needs to turn numbers into a picture
(guides/data-math-and-graphs.md). Plain Python, no numpy, so they work inside a script (which can't import) and in
Python next to the document alike.

    P = plot_area(x=(0, 10), y=(-1, 1), rect=(160, 140, 1600, 800))   # data units -> comp px (y up)
    pts = curve_points(math.sin, 0, 10, n=200)                        # [(x, y), …]; None where the function breaks
    path("wave", d=line_d(pts, to=P, smooth=True), fill="none", stroke=True)
    for v in nice_ticks(-1, 1): text(body=tick_label(v, nice_ticks(-1, 1)), x=P.x(0) - 20, y=P.y(v), align="right")
    V = view3d(yaw=35, pitch=25, scale=60, center=(960, 600))           # (x, y, z) -> comp px
    path("mesh", d=lines_d(surface_lines(lambda x, y: math.sin(x) * math.cos(y), (-3, 3), (-3, 3)), to=V), fill="none", stroke=True)

A point list may hold None: the line lifts there and starts again (a gap: 1/x at 0, tan at π/2).
"""
from __future__ import annotations

import math

from . import pathdata


def plot_area(x, y, rect):
    """A function (x, y) -> (px, py) mapping the data range x=(lo, hi), y=(lo, hi) onto rect=(left, top, w, h) in comp
    px, y up as on graph paper. `.x(v)` and `.y(v)` map one axis alone (tick and label places); `.rect` is the rect."""
    (x0, x1), (y0, y1), (left, top, w, h) = x, y, rect
    if x1 == x0 or y1 == y0:
        raise ValueError(f"plot_area: a range needs two different ends (x={tuple(x)}, y={tuple(y)})")
    fx = lambda v: left + (v - x0) / (x1 - x0) * w      # noqa: E731
    fy = lambda v: top + h - (v - y0) / (y1 - y0) * h   # noqa: E731

    def to(px, py):
        return fx(px), fy(py)
    to.x, to.y, to.rect = fx, fy, (left, top, w, h)
    return to


def _finite(v) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v)


def _run(f, t0, t1, n, pick, ylim=None):
    if n < 2:
        raise ValueError("n: at least 2 samples")
    out = []
    for i in range(n):
        t = t0 + (t1 - t0) * i / (n - 1)
        try:
            p = pick(t, f(t))
        except (ZeroDivisionError, ValueError, OverflowError):
            p = None
        ok = p is not None and all(_finite(c) for c in p) and (ylim is None or ylim[0] <= p[1] <= ylim[1])
        if ok:
            out.append(p)
        elif out and out[-1] is not None:
            out.append(None)
    while out and out[-1] is None:
        out.pop()
    return out


def curve_points(f, x0, x1, n=200, ylim=None):
    """y = f(x) sampled at n evenly spaced x from x0 to x1: [(x, y), …]. Where f fails or isn't a number (or y leaves
    `ylim`=(lo, hi)) the list has a None: a gap in the line."""
    return _run(f, x0, x1, n, lambda t, y: (t, y), ylim)


def param_points(f, t0, t1, n=200):
    """A parametric curve: f(t) -> (x, y) sampled at n evenly spaced t from t0 to t1."""
    return _run(f, t0, t1, n, lambda t, p: tuple(p))


def polar_points(r, a0=0.0, a1=2 * math.pi, n=360):
    """A polar curve r(θ), θ in radians from a0 to a1: [(r cos θ, r sin θ), …] (y up, as the maths reads it)."""
    return _run(r, a0, a1, n, lambda a, v: (v * math.cos(a), v * math.sin(a)))


def line_d(points, to=None, smooth=False, closed=False) -> str:
    """Path data through the points: straight lines, or `smooth` (a Catmull-Rom curve through every point, as cubic
    Béziers). `to` maps each point first (a plot_area, a view3d: to(*point)). None in the list lifts the pen."""
    runs, cur = [], []
    for p in points:
        if p is None:
            runs.append(cur)
            cur = []
        else:
            cur.append(tuple(to(*p)) if to else (float(p[0]), float(p[1])))
    runs.append(cur)
    cmds = []
    for run in (r for r in runs if r):
        cmds += _smooth(run, closed) if smooth and len(run) > 2 else _straight(run, closed)
    if not cmds:
        raise ValueError("line_d: no points to draw (every sample was a gap?)")
    return pathdata.write(cmds)


def lines_d(lines, to=None, smooth=False, closed=False) -> str:
    """Several lines (a grid, a wireframe, a family of curves) as one path's data: each its own piece."""
    return line_d([p for ln in lines for p in [*ln, None]], to, smooth, closed)


def _straight(run, closed):
    return [("M", *run[0])] + [("L", *p) for p in run[1:]] + ([("Z",)] if closed else [])


def _smooth(run, closed):
    n = len(run)
    at = (lambda k: run[k % n]) if closed else (lambda k: run[min(max(k, 0), n - 1)])   # open: the ends repeat
    cmds = [("M", *run[0])]
    for i in range(n if closed else n - 1):
        p0, p1, p2, p3 = at(i - 1), at(i), at(i + 1), at(i + 2)
        cmds.append(("C", p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6,
                     p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6, p2[0], p2[1]))
    return cmds + ([("Z",)] if closed else [])


def nice_ticks(lo, hi, count=5, extend=False):
    """Round tick values (steps of 1, 2 or 5 × a power of ten) about `count` of them, inside lo..hi; `extend`: the
    first and last tick reach past lo and hi instead, for an axis that should end on a round number."""
    if hi < lo:
        lo, hi = hi, lo
    if hi == lo:
        return [lo]
    raw = (hi - lo) / max(count, 1)
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw * 0.999)
    a, b = lo / step, hi / step                     # tiny slack: 0.30000000000000004 / 0.1 is still tick 3
    first, last = (math.floor(a + 1e-9), math.ceil(b - 1e-9)) if extend else (math.ceil(a - 1e-9), math.floor(b + 1e-9))
    whole = step >= 1                               # whole-number steps give whole numbers (labels read 20, not 20.0)
    return [int(round(k * step)) if whole else round(k * step, 12) + 0.0 for k in range(first, last + 1)]


def tick_label(v, ticks_or_step, separator="") -> str:
    """A tick's words with just the decimals its step needs (step 0.5 -> "1.5", step 2 -> "4", step 0.25 -> "0.75");
    pass the tick list or the step. `separator=","` groups thousands ("1,500"), matching a counter's countSeparator."""
    t = ticks_or_step
    step = abs(t[1] - t[0]) if isinstance(t, (list, tuple)) and len(t) > 1 else abs(t) if not isinstance(t, (list, tuple)) else 1
    places = 0
    while places < 9 and abs(step * 10 ** places - round(step * 10 ** places)) > 1e-6:
        places += 1
    text = f"{v:,.{places}f}".replace(",", separator)
    return text[1:] if text.startswith("-") and round(v, places) == 0 else text


def view3d(yaw=30.0, pitch=25.0, scale=100.0, center=(960, 540), distance=None):
    """A function (x, y, z) -> (px, py): the view of 3D points, z up. `yaw` turns round the up axis, `pitch` looks
    down from above (degrees); `scale` px per unit; `distance` (units) gives perspective, None a flat (orthographic) view."""
    cy_, sy_ = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))

    def to(x, y, z=0.0):
        rx, ry = x * cy_ - y * sy_, x * sy_ + y * cy_
        up, depth = ry * sp + z * cp, ry * cp - z * sp
        k = 1.0 if distance is None else distance / max(distance + depth, 1e-6)
        return center[0] + rx * scale * k, center[1] - up * scale * k
    return to


def surface_lines(f, x, y, lines=16, steps=48):
    """A surface z = f(x, y) over x=(lo, hi), y=(lo, hi) as a wireframe: `lines` lines along each axis, each sampled
    `steps` times, as 3D point lists (None where f fails) for lines_d(..., to=view3d(...))."""
    (x0, x1), (y0, y1) = x, y
    at = lambda lo, hi, i, n: lo + (hi - lo) * i / (n - 1)   # noqa: E731
    out = []
    for i in range(lines):
        a, b = at(x0, x1, i, lines), at(y0, y1, i, lines)
        out.append([_z(f, a, at(y0, y1, j, steps)) for j in range(steps)])
        out.append([_z(f, at(x0, x1, j, steps), b) for j in range(steps)])
    return out


def _z(f, x, y):
    try:
        z = f(x, y)
    except (ZeroDivisionError, ValueError, OverflowError):
        return None
    return (x, y, z) if _finite(z) else None


def for_script() -> dict:
    """The names a script gets (script.py): the helpers above and parse_table (table.py) for a table pasted as text."""
    from .table import parse_table
    return {f.__name__: f for f in (plot_area, curve_points, param_points, polar_points, line_d, lines_d, nice_ticks,
                                    tick_label, view3d, surface_lines, parse_table)}
