"""Flat outlines for the core to extrude (ENGINE_CONTRACT.md § 2, mesh shape "outline"): words, SVG drawings and 2D
path layers become [{"outer": [[x, y] …], "holes": [[[x, y] …] …]}] in metres on the item's XY plane, outer
counter-clockwise and holes clockwise seen from +Z, curves flattened, no repeated closing point.

One pipeline for all three: a shape is drawn into a skia-pathops Path (overlaps merged by `simplify`, so a variable font's
overlapping strokes and an SVG's stacked shapes come out as clean outlines), flattened, placed (scaled, centred, y flipped
when the source is y-down), and its contours are nested into outers and holes. Results are cached by inputs + file times.
"""
from __future__ import annotations

import math
from collections import OrderedDict
from pathlib import Path

import numpy as np
from fontTools.pens.basePen import BasePen

MIN_TOLERANCE = 1e-4          # metres: 0.1 mm, or 0.2% of the size when that is bigger
# The most a flattened curve turns from one straight piece to the next. Distance alone isn't enough: a polished bevel
# reflects the turn, not the distance, so a 4 cm circle cut to 0.2% (36 pieces, 10° each) showed every corner as a
# kink in its highlight and a polygon outline in close-up (H22). 2.5° = 144 pieces round a full circle.
MAX_TURN = math.radians(2.5)


def _turn(*legs) -> float:
    """How far a control polygon turns along its legs (an upper bound on the curve's own turning), in radians."""
    legs = [d for d in legs if math.hypot(*d) > 0]
    return sum(math.atan2(abs(a[0] * b[1] - a[1] * b[0]), a[0] * b[0] + a[1] * b[1]) for a, b in zip(legs, legs[1:]))
_CACHE: OrderedDict = OrderedDict()
CACHE_SIZE = 64


def _leg(a, b):
    return (b[0] - a[0], b[1] - a[1])


class Flatten(BasePen):
    """Collects a path's contours as point lists; curves are cut into lines no further than `tol` from the curve and
    turning at most MAX_TURN from one line to the next."""

    def __init__(self, tol: float):
        super().__init__(None)
        self.tol, self.contours, self._cur = tol, [], None

    def _moveTo(self, pt):
        self._cur = [pt]

    def _lineTo(self, pt):
        self._cur.append(pt)

    def _steps(self, flat: float, k: float, turn: float) -> int:
        return max(1, min(256, max(math.ceil(math.sqrt(k * flat / self.tol)), math.ceil(turn / MAX_TURN))))

    def _qCurveToOne(self, p1, p2):
        p0 = self._cur[-1]
        n = self._steps(math.hypot(p0[0] - 2 * p1[0] + p2[0], p0[1] - 2 * p1[1] + p2[1]), 0.25, _turn(_leg(p0, p1), _leg(p1, p2)))
        for i in range(1, n + 1):
            t = i / n
            a, b, c = (1 - t) ** 2, 2 * t * (1 - t), t * t
            self._cur.append((a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]))

    def _curveToOne(self, p1, p2, p3):
        p0 = self._cur[-1]
        d = max(math.hypot(p0[0] - 2 * p1[0] + p2[0], p0[1] - 2 * p1[1] + p2[1]),
                math.hypot(p1[0] - 2 * p2[0] + p3[0], p1[1] - 2 * p2[1] + p3[1]))
        n = self._steps(d, 0.75, _turn(_leg(p0, p1), _leg(p1, p2), _leg(p2, p3)))
        for i in range(1, n + 1):
            t = i / n
            a, b, c, e = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
            self._cur.append((a * p0[0] + b * p1[0] + c * p2[0] + e * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + e * p3[1]))

    def _closePath(self):
        if self._cur:
            self.contours.append(self._cur)
        self._cur = None

    _endPath = _closePath


def contours_of(path, tol: float) -> list[np.ndarray]:
    """A pathops Path (already simplified) → closed polygons as (n, 2) arrays, without the repeated last point."""
    pen = Flatten(tol)
    path.draw(pen)
    if pen._cur:
        pen._closePath()
    out = []
    for pts in pen.contours:
        a = np.array(pts, dtype=float)
        a = a[np.r_[True, np.any(np.diff(a, axis=0) != 0, axis=1)]] if len(a) > 1 else a
        if len(a) > 1 and np.array_equal(a[0], a[-1]):
            a = a[:-1]
        if len(a) >= 3:
            out.append(a)
    return out


def _area(a: np.ndarray) -> float:
    x, y = a[:, 0], a[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _inside(poly: np.ndarray, p) -> bool:
    x, y, px, py = poly[:, 0], poly[:, 1], p[0], p[1]
    x2, y2 = np.roll(x, -1), np.roll(y, -1)
    crossing = (y > py) != (y2 > py)
    with np.errstate(divide="ignore", invalid="ignore"):
        at = x + (py - y) * (x2 - x) / (y2 - y)
    return bool(np.count_nonzero(crossing & (px < at)) % 2)


def _within(inner: np.ndarray, outer: np.ndarray) -> bool:
    """`inner` lies inside `outer`: most of a few of its points are (a touching corner can't decide it alone)."""
    picks = inner[np.linspace(0, len(inner) - 1, min(5, len(inner))).astype(int)]
    return sum(_inside(outer, p) for p in picks) * 2 > len(picks)


def nest(polys: list[np.ndarray]) -> list[dict]:
    """Polygons → shapes: a polygon inside an even number of others is an outer, inside an odd number a hole of the
    smallest polygon around it. Outers come out counter-clockwise, holes clockwise."""
    polys = sorted(polys, key=lambda a: -abs(_area(a)))
    parents = [[j for j in range(i) if _within(polys[i], polys[j])] for i in range(len(polys))]
    shapes, owner = [], {}
    for i, p in enumerate(polys):
        hole = len(parents[i]) % 2 == 1
        ccw = _area(p) > 0
        pts = (p if ccw != hole else p[::-1]).round(7).tolist()
        if hole:
            shapes[owner[parents[i][-1]]]["holes"].append(pts)
        else:
            owner[i] = len(shapes)
            shapes.append({"outer": pts, "holes": []})
    return shapes


def place(contours: list[np.ndarray], scale: float, centre: tuple[float, float], flip: bool) -> list[np.ndarray]:
    k = np.array([scale, -scale if flip else scale])
    c = np.array(centre)
    return [(a - c) * k for a in contours]


def bounds(contours: list[np.ndarray]) -> tuple[float, float, float, float]:
    a = np.concatenate(contours)
    return float(a[:, 0].min()), float(a[:, 1].min()), float(a[:, 0].max()), float(a[:, 1].max())


def stamp(path: str) -> float:
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return 0.0


def cached(key: tuple, make):
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    _CACHE[key] = result = make()
    while len(_CACHE) > CACHE_SIZE:
        _CACHE.popitem(last=False)
    return result


def for_item(item: dict, folder=None) -> list[dict]:
    """The scene outline of a text / svg / path2d mesh item (its values as written in the document)."""
    from . import outline_svg, outline_text
    shape = item["shape"]
    if shape == "text":
        return outline_text.text_outline(item)
    if shape == "svg":
        return outline_svg.svg_outline(item)
    if shape == "path2d":
        return outline_svg.path2d_outline(item, folder)
    raise ValueError(f'"{shape}" has no outline (text, svg, path2d do)')
