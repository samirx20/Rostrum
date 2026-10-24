"""A drawing grows with its strokes, in any direction (2D camera spec § 4.11): a stroke reaching past the drawing's
canvas makes the canvas bigger so the whole stroke fits, in the same change as the stroke (one undo step). Nothing
already painted moves on screen:

- growing right or down: only w / h get bigger;
- growing left or up by (dx, dy): every stroke, fill outline and paint mask in every drawing of the layer moves by
  (+dx, +dy) in the canvas, the paper's grain with them (each drawing's paperX / paperY, rostrum_paint.canvas.origin),
  and so do the layer's own masks (own px);
- the anchor stays on the same canvas px: anchorX = (anchorX · old w + dx) / new w (every key too), so position,
  scale, turn and depth place everything exactly where it was.

Growth comes in STEP px chunks (it is rare: a few strokes past the edge need one). A drawing is at most MOST px a side
(fields.py w / h); a stroke that would grow it past that starts a new drawing beside it (paint_overflow.py). Paint on an
element never grows: it lives inside the element's box.
"""
from __future__ import annotations

import math

from rostrum_core.keys import keys_of

from . import fields as F

STEP = 256           # canvas px a drawing grows by at least, each side it grows
MOST = 8192          # canvas px a side at most (fields.py "w" / "h")
PAD = 4              # canvas px spare beyond the brush's reach


def reach(points, brush: dict) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1): the canvas px a stroke may paint, from its points and how far its brush reaches round them."""
    size = float(brush.get("size", 0))
    r = size / 2 * (1 + brush.get("size_jitter", 0) + brush.get("tilt_size", 0)) + 3 * brush.get("jitter", 0) * size + PAD
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs) - r, min(ys) - r, max(xs) + r, max(ys) + r


def need(w: int, h: int, box) -> tuple[int, int, int, int]:
    """(left, top, right, bottom): whole px the canvas (w × h) lacks for `box`, each 0 or more."""
    x0, y0, x1, y1 = box
    return (max(0, math.ceil(-x0)), max(0, math.ceil(-y0)), max(0, math.ceil(x1 - w)), max(0, math.ceil(y1 - h)))


def fits(w: int, h: int, box) -> bool:
    """Whether the canvas can grow to hold `box` and stay within MOST a side."""
    left, top, right, bottom = need(w, h, box)
    return w + left + right <= MOST and h + top + bottom <= MOST


def _chunks(size: int, lo: int, hi: int) -> tuple[int, int]:
    """The two sides' growth rounded up to STEP chunks, as far as MOST leaves room."""
    room = MOST - size - lo - hi
    out = []
    for n in (lo, hi):
        grown = min(math.ceil(n / STEP) * STEP, n + room) if n else 0
        room -= grown - n
        out.append(grown)
    return out[0], out[1]


def shifted(points, dx: float, dy: float) -> list:
    return [[round(p[0] + dx, 2), round(p[1] + dy, 2), *p[2:]] for p in points]


def grow(ctx, t: str, box) -> tuple[int, int]:
    """Grow drawing `t` so `box` (canvas px) fits (call `fits` first); (dx, dy): how far its canvas moved right and
    down, to add to any canvas point given before the growth."""
    item = ctx.item(t)
    w, h = int(item.get("w", 1920)), int(item.get("h", 1080))
    left, top, right, bottom = need(w, h, box)
    if not (left or top or right or bottom):
        return 0, 0
    left, right = _chunks(w, left, right)
    top, bottom = _chunks(h, top, bottom)
    nw, nh = w + left + right, h + top + bottom
    if left or top:
        _move_paint(ctx, item, left, top)
        _move_masks(ctx, item, left, top)
    set_anchor(ctx, t, "anchorX", lambda a: (a * w + left) / nw)
    set_anchor(ctx, t, "anchorY", lambda a: (a * h + top) / nh)
    ctx.set(t, "w", nw)
    ctx.set(t, "h", nh)
    return left, top


def set_anchor(ctx, t: str, prop: str, new) -> None:
    """The layer's anchor `prop` (its still value and every key) through `new(old fraction) -> fraction`."""
    item = ctx.item(t)
    ctx.set(t, prop, new(item.get(prop, F.defaults(item["type"])[prop])))
    for k in keys_of(item, prop):
        ctx.set(k["id"], "v", new(k["v"]))


def _move_paint(ctx, item: dict, dx: int, dy: int) -> None:
    for frame in item.get("frames", []):
        for paint in frame.get("paints", []):
            for s in paint.get("strokes", []):
                ctx.set(s["id"], "points", shifted(s["points"], dx, dy))
        for m in frame.get("paintmasks", []):
            if m.get("points"):
                ctx.set(m["id"], "points", shifted(m["points"], dx, dy))
        ctx.set(frame["id"], "paperX", int(frame.get("paperX", 0)) + dx)
        ctx.set(frame["id"], "paperY", int(frame.get("paperY", 0)) + dy)


def as_now(old_frame: dict, old_size: tuple[int, int], frame: dict, w: int, h: int):
    """An earlier state of a drawing (its frame at its canvas size then) as HxWx4 uint8 in the canvas it has now
    (w × h, the growth since moving it by the change of paperX / paperY), to compare with the drawing now."""
    import numpy as np
    from rostrum_paint import canvas
    px = canvas.rgba8(old_frame, *old_size)
    (ox, oy), (nx, ny) = canvas.origin(old_frame), canvas.origin(frame)
    dx, dy, out = nx - ox, ny - oy, np.zeros((h, w, 4), np.uint8)
    x0, y0, x1, y1 = max(0, dx), max(0, dy), min(w, dx + px.shape[1]), min(h, dy + px.shape[0])
    if x1 > x0 and y1 > y0:
        out[y0:y1, x0:x1] = px[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
    return out


def _move_masks(ctx, item: dict, dx: int, dy: int) -> None:
    """The layer's own masks are in its own px from its box's top-left: they move with the paint."""
    for m in item.get("masks", []):
        for prop, d in (("x", dx), ("y", dy)):
            if d:
                ctx.set(m["id"], prop, m.get(prop, F.defaults("mask").get(prop, 0.0)) + d)
                for k in keys_of(m, prop):
                    ctx.set(k["id"], "v", k["v"] + d)
