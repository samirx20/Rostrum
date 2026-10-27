"""Alt measuring on the canvas (CANVAS.md §2 row 23): the red lines and numbers from the one picked layer to the layer
under the pointer, or to the frame's edges when the pointer is over nothing. No Qt; world px throughout (composition px
at home), as bounds.extent gives the boxes (a turned layer is measured by the box round it, as Figma does).

    lines(a, b) -> [{"along": "x" | "y", "at": px, "from": px, "to": px, "gap": "48"} | {..., "guide": True}]

`a`: the picked layer's extent (x0, y0, x1, y1); `b`: the hovered layer's or the frame's. An "along x" line runs
across at y = at, from x = from to x = to; an "along y" line runs up and down at x = at. `gap` is the distance in words, as the snap
lines write it. A `guide` entry (no gap) is the thin line from a measuring line's end along to a box it doesn't reach.

- One box inside the other (the frame round the layer, a piece inside the picked group) or the two overlapping: the
  distance between each pair of matching edges on each axis, at the middle of where they overlap on the other axis.
- Apart on an axis: the one gap between them on it; at the middle of where they overlap on the other axis, or, apart
  on both, from the picked layer's middle with a guide to the other box. Overlapping on one axis but apart on the
  other: only that other axis's gap.
Zero distances draw nothing.
"""
from __future__ import annotations

_NONE = 0.05                  # px: closer than this is no distance


def words(d: float) -> str:
    """The distance as the snap lines write a gap: whole px, or one decimal when it isn't whole."""
    return f"{d:.0f}" if abs(d - round(d)) < _NONE else f"{d:.1f}"


def _line(i, at, lo, hi):
    return {"along": "xy"[i], "at": at, "from": lo, "to": hi, "gap": words(hi - lo)}


def _across(a, b, j):
    """Where a measuring line along the other axis sits on axis j, and whether a and b are apart on j: the middle of
    their overlap on j, or a's middle when they don't overlap there."""
    lo, hi = max(a[j], b[j]), min(a[j + 2], b[j + 2])
    return ((lo + hi) / 2, False) if lo <= hi else ((a[j] + a[j + 2]) / 2, True)


def lines(a, b) -> list[dict]:
    out: list[dict] = []
    for i in (0, 1):                      # i: the axis measured along; j: the other one, where the line sits
        j = 1 - i
        at, apart = _across(a, b, j)
        if b[i] >= a[i + 2] or a[i] >= b[i + 2]:              # apart along i: the one gap
            lo, hi = (a[i + 2], b[i]) if b[i] >= a[i + 2] else (b[i + 2], a[i])
            if hi - lo < _NONE:
                continue
            out.append(_line(i, at, lo, hi))
            if apart:                     # the line runs from a's middle: a guide along j to b's near edge
                end = b[j] if b[j] > at else b[j + 2]
                out.append({"along": "xy"[j], "at": hi if b[i] >= a[i + 2] else lo,
                            "from": min(at, end), "to": max(at, end), "guide": True})
            continue
        if apart:                         # side by side along i, apart along j: only j's gap says anything
            continue
        for k in (0, 2):                  # overlapping along i: each pair of matching edges
            lo, hi = sorted((a[i + k], b[i + k]))
            if hi - lo >= _NONE:
                out.append(_line(i, at, lo, hi))
    return out
