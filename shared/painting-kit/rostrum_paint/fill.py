"""Fill: a closed area of a painting filled with one colour, kept as a **shape** (its outline), never as pixels, so it
stays as sharp as the strokes around it and replays like them.

    rings = region(alpha, at, gap)     the outline of the area around `at`, found in the paint's coverage
    fill.lay(layer, item, rgb, mask)   the fill item laid on a paint layer like one normal stroke (canvas.stamp)

Finding the area (`region`): the lines are where the paint covers at least half; **Close gaps** thickens them by
`gap` px first, so lines that don't quite meet still close the area; the area is then grown back by `gap` px plus
one, so it tucks under the lines (no light seam between line and colour). An area that reaches the canvas's edge is
not closed: `NotClosed` says so (never a fill of the whole canvas). On a seamless canvas (`wrap`, wrap.py) the edges
are joined: an area closed only across them is closed, and it is filled on both sides; only a canvas with no lines at
all has nothing to close it. The outline is traced along pixel edges and
simplified; each point is [x, y, ring]: ring 0 is the outside, 1, 2 … are holes (a closed shape inside the area).
"""
from __future__ import annotations

import numpy as np

from .marks import Coverage, apply_paint

GAPS = {"small": 3, "medium": 6, "large": 12}      # Close gaps: lines this far apart (twice the px) still close


class NotClosed(ValueError):
    """The click is on a line, or its area is not closed (it reaches the canvas's edge). `plain`: what to tell a person."""

    def __init__(self, message: str, plain: str = ""):
        super().__init__(message)
        self.plain = plain


def _grow(m: np.ndarray, r: int, wrap: bool = False) -> np.ndarray:
    """m thickened by about r px, roundly (one px at a time, crosses and squares in turn: an octagon, so a closed gap
    has round ends like the brush's, not square corners). `wrap`: across the joined edges too."""
    if wrap:            # grown on the canvas with r px of the opposite sides round it, then cut back
        return _grow(np.pad(m, r, mode="wrap"), r)[r:r + m.shape[0], r:r + m.shape[1]] if r else m.copy()
    out = m.copy()
    for i in range(r):
        src = out.copy()
        out[1:] |= src[:-1]
        out[:-1] |= src[1:]
        out[:, 1:] |= src[:, :-1]
        out[:, :-1] |= src[:, 1:]
        if i % 2:
            out[1:, 1:] |= src[:-1, :-1]
            out[:-1, :-1] |= src[1:, 1:]
            out[1:, :-1] |= src[:-1, 1:]
            out[:-1, 1:] |= src[1:, :-1]
    return out


def _runs(free: np.ndarray, reached: np.ndarray) -> np.ndarray:
    """reached spread along each row's free runs (a run touched anywhere is reached all along)."""
    h, w = free.shape
    f = free.ravel()
    start = f.copy()
    start[1:] &= ~f[:-1]
    start[::w] = f[::w]
    ids = np.cumsum(start) * f
    hit = np.zeros(int(ids.max()) + 1, bool)
    hit[ids[reached.ravel() & f]] = True
    hit[0] = False
    return hit[ids].reshape(h, w)


def _flood(free: np.ndarray, x: int, y: int, wrap: bool = False) -> np.ndarray:
    """The free pixels connected to (x, y), 4-neighbours: row and column spreads until nothing changes (`wrap`: and
    across the joined edges)."""
    got = np.zeros_like(free)
    got[y, x] = True
    while True:
        new = _runs(free.T.copy(), _runs(free, got).T.copy()).T
        if wrap:
            new[:, 0] |= new[:, -1] & free[:, 0]
            new[:, -1] |= new[:, 0] & free[:, -1]
            new[0] |= new[-1] & free[0]
            new[-1] |= new[0] & free[-1]
        if (new == got).all():
            return got
        got = new


def region(alpha: np.ndarray, at, gap: str = "small", wrap: bool = False) -> list[list[float]]:
    """The outline ([[x, y, ring], …], canvas px) of the closed area around `at` = (x, y) in the coverage `alpha`
    (HxW 0..1: every paint layer the fill should stop at); `wrap`: a seamless canvas. Raises NotClosed."""
    if gap not in GAPS:
        raise ValueError(f"gap must be one of {', '.join(GAPS)}, got {gap!r}")
    h, w = alpha.shape
    x, y = int(np.floor(at[0])), int(np.floor(at[1]))
    if not (0 <= x < w and 0 <= y < h):
        raise NotClosed(f"({at[0]:g}, {at[1]:g}) is outside the painting ({w}×{h} px)", "That click is outside the drawing.")
    r = GAPS[gap]
    line = alpha >= 0.5
    walls = _grow(line, r, wrap)
    if walls[y, x]:
        raise NotClosed(f"({at[0]:g}, {at[1]:g}) is on a line (or within the {gap} gap of one): click inside an area",
                        "That click is on a line. Click inside an area instead.")
    if wrap and not line.any():
        raise NotClosed("the seamless painting has no lines to close an area", "There are no lines here to fill inside.")
    area = _flood(~walls, x, y, wrap)
    if not wrap and (area[0].any() or area[-1].any() or area[:, 0].any() or area[:, -1].any()):
        raise NotClosed(f"the area at ({at[0]:g}, {at[1]:g}) is not closed: it reaches the edge of the painting "
                        f"(close the lines, or a larger Close gaps)",
                        "This area isn't closed: it runs out to the drawing's edge. Close the gap, or raise Close gaps.")
    area = _grow(_grow(area, r, wrap) & ~line, 1, wrap)
    return [[float(px), float(py), ring] for ring, loop in enumerate(_loops(area)) for px, py in loop]


def _loops(m: np.ndarray) -> list[list[tuple]]:
    """The area's boundary as closed loops along pixel edges (area on the left), outside first, simplified."""
    p = np.pad(m, 1)
    edges = {}
    ys, xs = np.nonzero(p[1:, 1:-1] & ~p[:-1, 1:-1])            # top edges, walked right to left
    for y, x in zip(ys, xs):
        edges.setdefault((x + 1, y), []).append((x, y))
    ys, xs = np.nonzero(p[:-1, 1:-1] & ~p[1:, 1:-1])            # bottom edges, left to right
    for y, x in zip(ys, xs):
        edges.setdefault((x, y), []).append((x + 1, y))
    ys, xs = np.nonzero(p[1:-1, 1:] & ~p[1:-1, :-1])            # left edges, top to bottom
    for y, x in zip(ys, xs):
        edges.setdefault((x, y), []).append((x, y + 1))
    ys, xs = np.nonzero(p[1:-1, :-1] & ~p[1:-1, 1:])            # right edges, bottom to top
    for y, x in zip(ys, xs):
        edges.setdefault((x, y + 1), []).append((x, y))
    loops = []
    while edges:
        start = next(iter(edges))
        loop, at, came = [start], start, None
        while True:
            outs = edges[at]
            nxt = outs.pop(_turn(outs, came, at) if len(outs) > 1 else 0)
            if not outs:
                del edges[at]
            came, at = (nxt[0] - at[0], nxt[1] - at[1]), nxt
            if at == start:
                break
            loop.append(at)
        loops.append(_simplify(loop))
    loops.sort(key=lambda lp: -abs(_area(lp)))                  # the outside is the largest
    return [lp for lp in loops if len(lp) >= 3]


def _turn(outs, came, at) -> int:
    """At a corner where two areas touch, keep turning the same way (left), so loops never cross."""
    if came is None:
        return 0
    left = (came[1], -came[0])
    return next((i for i, o in enumerate(outs) if (o[0] - at[0], o[1] - at[1]) == left), 0)


def _area(loop) -> float:
    a = np.asarray(loop, float)
    return 0.5 * float(np.sum(a[:, 0] * np.roll(a[:, 1], -1) - np.roll(a[:, 0], -1) * a[:, 1]))


def _simplify(loop, tol: float = 0.75) -> list[tuple]:
    """Fewer points, within `tol` px of the traced edge (the pixel stairs become straight slopes)."""
    pts = np.asarray(loop, float)
    if len(pts) < 4:
        return [tuple(q) for q in pts]
    far = int(np.argmax(((pts - pts[0]) ** 2).sum(1)))
    return _dp(pts[:far + 1], tol)[:-1] + _dp(np.vstack([pts[far:], pts[:1]]), tol)[:-1]


def _dp(pts, tol) -> list[tuple]:
    keep, stack = np.zeros(len(pts), bool), [(0, len(pts) - 1)]
    keep[[0, -1]] = True
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = pts[i], pts[j]
        d = b - a
        n = np.hypot(*d) or 1.0
        off = np.abs(d[0] * (pts[i + 1:j, 1] - a[1]) - d[1] * (pts[i + 1:j, 0] - a[0])) / n
        k = int(np.argmax(off))
        if off[k] > tol:
            keep[i + 1 + k] = True
            stack += [(i, i + 1 + k), (i + 1 + k, j)]
    return [(round(float(x), 2), round(float(y), 2)) for x, y in pts[keep]]


def coverage(points, w: int, h: int) -> np.ndarray:
    """A fill's outline ([[x, y, ring], …]) as HxW float32 0..1, antialiased (4×4 samples a pixel); holes cut out. A
    ring wound like ring 0 is another outside (an area cut by a seamless canvas's edges is in pieces), one wound the
    other way a hole: outsides first, then holes."""
    a = np.zeros((h, w), np.float32)
    got = coverage_box(points, w, h)
    if got is not None:
        c, (x0, y0, x1, y1) = got
        a[y0:y1, x0:x1] = c
    return a


def coverage_box(points, w: int, h: int):
    """`coverage` drawn only over the outline's own whole-pixel box on the canvas: (HxW of that box, (x0, y0, x1, y1)),
    or None when it misses the canvas. The same samples as the whole canvas (the box starts on a pixel), without a
    4x-size picture of a big canvas for every fill (production round: a painted look took ~19 s a moment)."""
    from PIL import Image, ImageDraw
    ss = 4
    rings: dict[int, list] = {}
    for q in points:
        rings.setdefault(int(q[2]) if len(q) > 2 else 0, []).append((q[0], q[1]))
    rings = {k: v for k, v in rings.items() if len(v) >= 3}
    if not rings:
        return None
    xs = [x for v in rings.values() for x, _ in v]
    ys = [y for v in rings.values() for _, y in v]
    x0, y0 = max(0, int(np.floor(min(xs))) - 1), max(0, int(np.floor(min(ys))) - 1)
    x1, y1 = min(w, int(np.ceil(max(xs))) + 2), min(h, int(np.ceil(max(ys))) + 2)
    if x1 <= x0 or y1 <= y0:
        return None
    im = Image.new("L", ((x1 - x0) * ss, (y1 - y0) * ss), 0)
    draw = ImageDraw.Draw(im)
    wound = {k: _area(v) > 0 for k, v in rings.items()}
    outside = wound.get(0)
    for ring in sorted(rings, key=lambda k: (wound[k] != outside, k)):
        draw.polygon([((x - x0) * ss, (y - y0) * ss) for x, y in rings[ring]], fill=255 if wound[ring] == outside else 0)
    return np.asarray(im.reduce(ss), np.float32) / 255, (x0, y0, x1, y1)


def lay(layer_px, s: dict, rgb, mask=None):
    """A fill item laid like one stroke of the normal mode: its outline's coverage times its opacity (and mask)."""
    h, w = layer_px.shape[:2]
    got = coverage_box(s["points"], w, h)
    if got is None:
        return None
    a, (bx, by, bx1, by1) = got
    a = a * np.float32(s["opacity"])
    if mask is not None:
        a = a * mask[by:by1, bx:bx1]
    ys, xs = np.nonzero(a > 0)
    if not len(ys):
        return None
    x0, y0, x1, y1 = bx + int(xs.min()), by + int(ys.min()), bx + int(xs.max()) + 1, by + int(ys.max()) + 1
    c1 = np.ascontiguousarray(a[y0 - by:y1 - by, x0 - bx:x1 - bx])
    apply_paint(layer_px[y0:y1, x0:x1], np.zeros_like(c1), c1, np.asarray(rgb, np.float32), "normal")
    return Coverage(c1, (x0, y0, x1, y1))
