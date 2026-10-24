"""Snapping on the canvas (UX_SPEC 6.2, INTERACTION 1.11): where a moving box lands when one of its edges or centre
lines comes within the snap distance of the frame's or another layer's. No Qt; composition px throughout.

    snap(box, targets, threshold, xs=ALL, ys=ALL) -> (dx, dy, lines)

`box`: the moving box's extent (x0, y0, x1, y1) where the pointer would put it. `targets`: [(rank, (x0, y0, x1, y1))],
what it may catch; a lower rank wins over a nearer line of a higher rank (frame_target() is rank 0: the frame's edges
and centre lines come first; then the same group's layers, then the rest). `threshold`: the snap distance in composition
px, i.e. DISTANCE screen px / the view's zoom (threshold()). `xs` / `ys`: which of the box's lines may snap, 0 the start
edge, 1 the centre, 2 the end edge (a move: all; a resize: the dragged edge only; () = that axis doesn't snap).
Returns the offset to add to the move (0 when nothing is near) and the lines caught, for the magenta feedback:
[{"axis": "x" | "y", "at": px, "from": px, "to": px}] (an "x" line is vertical at x = at, from y = from to y = to).

Callers: drags (move, screen2d/snapper.py), the resize handles; a shape being drawn can call it the same way with
its growing box and xs / ys = its moving corner's edges. Ctrl after the press (no snapping) and Shift (straight) are the
caller's: it simply doesn't call snap, or passes () for the locked axis. Snapping never changes a typed value: only
drags call it.
"""
from __future__ import annotations

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


def _axis(box, targets, limit, which, a):
    """Best offset on one axis (a = 0: x, 1: y) and the targets it lines up with."""
    lo, hi = (0, 2) if a == 0 else (1, 3)
    mine = _lines((box[lo], 0, box[hi]), which)
    best = None
    for rank, t in targets:
        for _, at in _lines((t[lo], 0, t[hi]), ALL):
            for _, m in mine:
                d = at - m
                if abs(d) <= limit and (best is None or (rank, abs(d)) < best[:2]):
                    best = (rank, abs(d), d)
    if best is None:
        return 0.0, []
    d = best[2]
    hits = []
    for _, t in targets:
        for _, at in _lines((t[lo], 0, t[hi]), ALL):
            if any(abs(at - (m + d)) <= _SAME for _, m in mine):
                hits.append((at, t))
    return d, hits


def snap(box, targets, threshold, xs=ALL, ys=ALL):
    dx, hx = _axis(box, targets, threshold, xs, 0)
    dy, hy = _axis(box, targets, threshold, ys, 1)
    moved = (box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy)
    lines = []
    for at, t in hx:
        lines.append({"axis": "x", "at": at, "from": min(moved[1], t[1]), "to": max(moved[3], t[3])})
    for at, t in hy:
        lines.append({"axis": "y", "at": at, "from": min(moved[0], t[0]), "to": max(moved[2], t[2])})
    return dx, dy, lines


def straight(dx: float, dy: float) -> tuple[float, float]:
    """Shift while dragging: keep the move on its main axis so far."""
    return (dx, 0.0) if abs(dx) >= abs(dy) else (0.0, dy)
