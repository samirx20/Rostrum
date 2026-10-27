"""Snapping on the canvas (UX_SPEC 6.2, INTERACTION 1.11): where a moving box lands when one of its edges or centre
lines comes within the snap distance of the frame's or another layer's. No Qt; composition px throughout.

    snap(box, targets, threshold, xs=ALL, ys=ALL, spaced=None) -> (dx, dy, lines)
    gaps(boxes, axis) -> [(a, b, gap)]        base G: neighbours along an axis (spec 2d-pro-workflows §2)
    even(boxes, axis) -> gap | None           the one gap when boxes in a run along an axis sit equally apart

`box`: the moving box's extent (x0, y0, x1, y1) where the pointer would put it. `targets`: [(rank, (x0, y0, x1, y1))],
what it may catch; a lower rank wins over a nearer line of a higher rank (frame_target() is rank 0: the frame's edges
and centre lines come first; then the same group's layers, then the rest). `threshold`: the snap distance in composition
px, i.e. DISTANCE screen px / the view's zoom (threshold()). `xs` / `ys`: which of the box's lines may snap, 0 the start
edge, 1 the centre, 2 the end edge (a move: all; a resize: the dragged edge only; () = that axis doesn't snap).
Returns the offset to add to the move (0 when nothing is near) and the lines caught, for the magenta feedback:
[{"axis": "x" | "y", "at": px, "from": px, "to": px, "what": "centre" | "edge"}] (an "x" line is vertical at x = at,
from y = from to y = to; `what` is the word on it, what it caught), at most one per axis (the nearest caught layer). A line to a neighbour in line also has `gap` (its words, "24") and
`gapAt` (where along the line the gap's middle is, 0..1). `spaced` (spacing(targets), worked out once at the press) adds
equal gaps to a move: the box may also land where its gap to a neighbour equals a gap between two other layers in its
row or column, or midway between its two neighbours; that ranks with the other layers (2). Each gap shown is then a
`mark` entry (a short bracket over the gap, with `gap` and `gapAt` 0.5); at most two show, of one axis.

Callers: drags (move, screen2d/snapper.py), the resize handles; a shape being drawn can call it the same way with
its growing box and xs / ys = its moving corner's edges. Ctrl after the press (no snapping) and Shift (straight) are the
caller's: it simply doesn't call snap, or passes () for the locked axis. Snapping never changes a typed value: only
drags call it.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right

DISTANCE = 6.0                 # screen px, at any zoom (one number for one feel, INTERACTION 1.11)
ALL = (0, 1, 2)
_SAME = 0.5                    # composition px: lines this close to the caught one are shown as caught too


def threshold(zoom: float) -> float:
    """The snap distance in composition px at `zoom` screen px per composition px."""
    return DISTANCE / max(zoom, 1e-6)


def frame_target(w: float, h: float, cam=None) -> tuple[int, tuple]:
    """The frame as rank 0: its box where it is (`cam`: the frame's Shot at the playhead, frame/view.py; none: the
    output rectangle at home). The box is width/zoom x height/zoom about the frame's centre (swapped at 90 / 270 deg).
    A frame turned by anything else is only its centre point for now (the turned snap line is spec 9)."""
    if cam is None:
        return (0, (0.0, 0.0, float(w), float(h)))
    k = (cam.roll / 90.0) % 4
    if abs(k - round(k)) > 1e-6:
        return (0, (cam.x, cam.y, cam.x, cam.y))
    hw, hh = (w, h) if round(k) % 2 == 0 else (h, w)
    hw, hh = hw / cam.zoom / 2, hh / cam.zoom / 2
    return (0, (cam.x - hw, cam.y - hh, cam.x + hw, cam.y + hh))


def _lines(b, which):
    return [(i, (b[0], (b[0] + b[2]) / 2, b[2])[i]) for i in which]


def _over(a, b, j):
    """a and b share some of axis j (0 x, 1 y)."""
    return a[j] < b[j + 2] and b[j] < a[j + 2]


def gaps(boxes, axis):
    """Base G: [(a, b, gap)] for each box `a` and its nearest neighbour `b` after it along `axis` ("x" or "y") among
    the boxes overlapping it on the other axis; gap = b's start - a's end (>= 0). Boxes are extents (x0, y0, x1, y1)."""
    i = 0 if axis == "x" else 1
    run = sorted(boxes, key=lambda b: b[i])         # by start: the first overlapping one past a's end is the nearest
    starts = [b[i] for b in run]                    # (comparing every pair was ~25 ms a press at 200 layers)
    out = []
    for a in boxes:
        b = next((b for b in run[bisect_left(starts, a[i + 2]):] if b is not a and _over(a, b, 1 - i)), None)
        if b is not None:
            out.append((a, b, b[i] - a[i + 2]))
    return out


def even(boxes, axis, tol=_SAME):
    """The gap between boxes in a run along `axis` (sorted by where they start, as layer.distribute does) when every
    gap is the same within `tol` px; None when they differ or there are fewer than two boxes."""
    i = 0 if axis == "x" else 1
    run = sorted((b[i], b[i + 2]) for b in boxes)
    sizes = [b[0] - a[1] for a, b in zip(run, run[1:])]
    return sum(sizes) / len(sizes) if sizes and max(sizes) - min(sizes) <= tol else None


def spacing(targets):
    """What equal-gap snapping needs, worked out once at a drag's press: the layers (rank 1 and 2, not the frame) and
    their gaps along each axis."""
    boxes = [t for rank, t in targets if rank > 0]
    return {"boxes": boxes, "x": [g for g in gaps(boxes, "x") if g[2] > 0], "y": [g for g in gaps(boxes, "y") if g[2] > 0]}


def _words(g):
    return f"{g:.0f}" if abs(g - round(g)) < 0.05 else f"{g:.1f}"


def _mark(a, b, i):
    """The bracket over the gap from a's end to b's start along axis i, midway across where they overlap."""
    j = 1 - i
    mid = (max(a[j], b[j]) + min(a[j + 2], b[j + 2])) / 2
    return {"axis": "xy"[j], "at": mid, "from": a[i + 2], "to": b[i], "gap": _words(b[i] - a[i + 2]), "gapAt": 0.5, "mark": True}


def _equal(box, sp, limit, i):
    """The nearest equal-gap landing along axis i within `limit`: (offset, [(a, b) gaps to mark, the box as None])."""
    j, best = 1 - i, None
    row = [b for b in sp["boxes"] if _over(box, b, j)]
    before = max((b for b in row if b[i + 2] <= box[i] + limit), key=lambda b: b[i + 2], default=None)
    after = min((b for b in row if b[i] >= box[i + 2] - limit), key=lambda b: b[i], default=None)
    found = []
    if before is not None and after is not None and after[i] - before[i + 2] >= box[i + 2] - box[i]:
        found.append((before[i + 2] + (after[i] - before[i + 2] - (box[i + 2] - box[i])) / 2 - box[i], [(before, None), (None, after)]))
    for a, b, g in sp["xy"[i]]:
        if (a is before and b is after) or not (_over(box, a, j) and _over(box, b, j)):
            continue
        if before is not None and a is not before:
            found.append((before[i + 2] + g - box[i], [(before, None), (a, b)]))
        if after is not None and b is not after:
            found.append((after[i] - g - box[i + 2], [(None, after), (a, b)]))
    for d, pairs in found:
        if abs(d) <= limit and (best is None or abs(d) < abs(best[0])):
            best = (d, pairs)
    return best


class _Lines:
    """Every target's three lines on each axis, sorted by where they are, made once per list of targets (a drag's
    press): a move looks up only the lines within the snap distance (bisect) instead of every layer's (200 layers:
    ~2-3 ms of each move)."""
    __slots__ = ("targets", "ats", "rows")

    def __init__(self, targets):
        self.targets, self.ats, self.rows = targets, [], []
        for lo, hi in ((0, 2), (1, 3)):
            rows = sorted((at, n, k, rank, t) for n, (rank, t) in enumerate(targets)
                          for k, at in _lines((t[lo], 0, t[hi]), ALL))
            self.rows.append(rows)
            self.ats.append([r[0] for r in rows])

    def near(self, a, lo, hi):
        """The lines of axis a from lo to hi (inclusive), as (at, order, line, rank, target)."""
        ats = self.ats[a]
        return self.rows[a][bisect_left(ats, lo):bisect_right(ats, hi)]


_KEPT = [None]                 # the last targets' _Lines (one drag at a time; held, so its id stays its own)


def _index(targets) -> _Lines:
    if _KEPT[0] is None or _KEPT[0].targets is not targets:
        _KEPT[0] = _Lines(targets)
    return _KEPT[0]


def _axis(box, targets, limit, which, a):
    """Best snap on one axis (a = 0: x, 1: y): ((rank, distance), offset, the targets it lines up with); None."""
    lo, hi = (0, 2) if a == 0 else (1, 3)
    mine = _lines((box[lo], 0, box[hi]), which)
    if not mine:
        return None
    index, best = _index(targets), None
    for _, m in mine:
        for at, n, k, rank, t in index.near(a, m - limit, m + limit):
            d = at - m
            if abs(d) <= limit and (best is None or (rank, abs(d), n, k) < best[:2] + best[3:]):
                best = (rank, abs(d), d, n, k)
    if best is None:
        return None
    d = best[2]
    hits = sorted({(n, k): (at, t, k) for _, m in mine for at, n, k, _, t in index.near(a, m + d - _SAME, m + d + _SAME)}.items())
    return best[:2], d, [h for _, h in hits]


def _what(at, t, k, moved, a) -> str:
    """The word a caught line says (CANVAS.md §2 row 24): "centre" when it is the caught box's middle (`k` 1, or a
    box of no size there: the turned frame's centre point) or the moving box's own middle; else "edge"."""
    lo, hi = (0, 2) if a == 0 else (1, 3)
    mid = moved[hi] - moved[lo] > _SAME and abs(at - (moved[lo] + moved[hi]) / 2) < _SAME
    return "centre" if k == 1 or t[hi] - t[lo] <= _SAME or mid else "edge"


def _line(at, t, k, moved, a):
    """The magenta line at `at` on axis a (0: a vertical line) from the moved box to t, saying what it caught (`what`),
    with the gap between them along it when they don't overlap there."""
    j = 1 - a
    lo, hi = min(moved[j], t[j]), max(moved[j + 2], t[j + 2])
    out = {"axis": "xy"[a], "at": at, "from": lo, "to": hi, "what": _what(at, t, k, moved, a)}
    start, end = (moved[j + 2], t[j]) if t[j] >= moved[j + 2] else (t[j + 2], moved[j])
    if end - start > _SAME and hi > lo:
        out.update(gap=_words(end - start), gapAt=((start + end) / 2 - lo) / (hi - lo))
    return out, max(end - start, 0.0)


def _nearest(hits, moved, a):
    """The one line of an axis: to the nearest caught box (one it touches or overlaps along the line is nearest)."""
    lines = [_line(at, t, k, moved, a) for at, t, k in hits]
    return [min(lines, key=lambda l: l[1])[0]] if lines else []


def snap(box, targets, threshold, xs=ALL, ys=ALL, spaced=None):
    found = [_axis(box, targets, threshold, which, a) for a, which in enumerate((xs, ys))]
    equal = [_equal(box, spaced, threshold, a) if spaced and which == ALL else None for a, which in enumerate((xs, ys))]
    if equal[0] and equal[1]:              # two gap marks at most: the nearer axis keeps its equal gap
        equal[abs(equal[0][0]) <= abs(equal[1][0])] = None
    use = [e if e and (f is None or (2, abs(e[0])) < f[0]) else None for e, f in zip(equal, found)]
    d = [u[0] if u else f[1] if f else 0.0 for u, f in zip(use, found)]
    moved = (box[0] + d[0], box[1] + d[1], box[2] + d[0], box[3] + d[1])
    lines = []
    for a in (0, 1):
        if use[a]:
            lines += [_mark(p or moved, q or moved, a) for p, q in use[a][1]]
        elif found[a]:                     # its gap runs along the other axis: brackets there already say it
            lines += [{k: v for k, v in l.items() if k not in ("gap", "gapAt")} if use[1 - a] else l
                      for l in _nearest(found[a][2], moved, a)]
    return d[0], d[1], lines


def straight(dx: float, dy: float) -> tuple[float, float]:
    """Shift while dragging: keep the move on its main axis so far."""
    return (dx, 0.0) if abs(dx) >= abs(dy) else (0.0, dy)
