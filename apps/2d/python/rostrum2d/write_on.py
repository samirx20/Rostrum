"""Drawn so far (paint_fields.DRAWN, After Effects' Write-on for paint): a drawing, or the paint on an element, painted
on over time. At an amount between 0 and 1 the drawing shows its strokes and fills in the order they were painted
(bottom paint layer first, each layer's in its order), the pen moving at one speed: each mark takes as long as its path
is long (a dot as long as its tip is wide), and the mark the pen is on shows as far as the pen has got along it.

The picture is made where every drawing's picture is made (the painting kit's pixels, the engine only reads PNGs), so
the canvas, the looks and the export show the same frames. At an amount the picture is the drawing's own pixels with
its first k marks laid (`before`) and with k + 1 (`after`), and between them the pixels of mark k as far as the pen
got: a pixel is shown once the pen passes a point of the path whose tip reaches it (the union of the tip's discs so
far, `_order`), so the head of the stroke is round like the brush, never a straight cut through a dab, and what shows
is the stroke's own finished paint (its bristles, grain and taper don't change as it grows). A fill fades in over its
share. The pictures are content-keyed files in the paint cache, one per frame where the amount is between 0 and 1.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
from collections import OrderedDict

import numpy as np
from rostrum_core.cache import CACHE, cache_key
from rostrum_paint import canvas, ink, shape

from .paint_fields import DRAWN

VERSION = "rostrum2d-drawn-so-far@1"
_ORDERS: OrderedDict = OrderedDict()     # (stroke's hash, box) -> (order px, step, length): a stroke's reveal, made once
_LOCK = threading.Lock()


def amount_at(item: dict, t: float) -> float:
    """Drawn so far at t (0..1), to 4 places (one picture per 1/10000)."""
    from .evaluate import value_at
    return round(min(1.0, max(0.0, float(value_at(item, DRAWN, t)))), 4)


def _length(s: dict) -> float:
    pts = np.asarray([q[:2] for q in s.get("points", [])], float)
    run = float(np.hypot(*np.diff(pts, axis=0).T).sum()) if len(pts) > 1 else 0.0
    return run + (float(s.get("size", 12.0)) if s.get("type") == "stroke" else 0.0)


def marks(frame: dict) -> list[tuple[int, int, float]]:
    """[(paint layer index, mark index, its share of the pen's time)] in drawing order. A hidden layer's take none."""
    return [(li, si, _length(s) if paint.get("visible", True) else 0.0)
            for li, paint in enumerate(frame.get("paints", [])) for si, s in enumerate(paint.get("strokes", []))]


def cut(frame: dict, amount: float) -> tuple[int, float]:
    """(k, f): at `amount` of the drawing, its first k marks are whole and mark k is f (0..1) drawn."""
    got = marks(frame)
    goal, at = max(0.0, amount) * sum(w for *_, w in got), 0.0
    if amount < 1:
        for k, (_, _, w) in enumerate(got):
            if w > 0 and at + w > goal:
                return k, (goal - at) / w
            at += w
    return len(got), 0.0


def _prefix(frame: dict, k: int) -> dict:
    """The drawing with only its first k marks (the same stroke items: the kit reuses its kept states of them)."""
    keep: dict = {}
    for li, si, _ in marks(frame)[:k]:
        keep[li] = si + 1
    return {**frame, "paints": [{**p, "strokes": p["strokes"][:keep.get(li, 0)]} for li, p in enumerate(frame.get("paints", []))]}


def _order(s: dict, box: tuple) -> tuple[np.ndarray, float, float]:
    """(per px of `box` [x0, y0, x1, y1]: how far along the path, in px, the pen is when its tip first reaches it; the
    step between the path's points looked at; the path's length). The tip's radius follows the pressure as the brush's
    does; px the tip never reaches (scatter) come in at the end."""
    key = (hashlib.sha1(json.dumps(s, sort_keys=True).encode("utf-8")).hexdigest(), box)
    with _LOCK:
        if key in _ORDERS:
            _ORDERS.move_to_end(key)
            return _ORDERS[key]
    x0, y0, x1, y1 = box
    pts = shape.steady(shape.points(s["points"]), float(s.get("steady", 0.0)))
    size, sp = float(s["size"]), float(s.get("size_pressure", 0.8))
    seg = np.hypot(*np.diff(pts[:, :2], axis=0).T) if len(pts) > 1 else np.zeros(0)
    L = np.concatenate([[0.0], np.cumsum(seg)])
    step = float(np.clip(size / 8, 1.0, 24.0))
    ts = np.append(np.arange(0.0, L[-1], step), L[-1]) if L[-1] > 0 else np.zeros(1)
    X, Y, P = (np.interp(ts, L, pts[:, i]) if L[-1] > 0 else pts[:1, i] for i in range(3))
    R = np.maximum(size / 2 * (1 - sp * (1 - P)), 0.5)
    pad = 2 * float(s.get("jitter", 0.0)) * size + 0.25 * size + 3
    order = np.full((y1 - y0, x1 - x0), np.inf, np.float32)
    for x, y, r, t in zip(X.tolist(), Y.tolist(), R.tolist(), ts.tolist()):
        bx0, bx1 = max(x0, math.floor(x - r - pad)), min(x1, math.ceil(x + r + pad) + 1)
        by0, by1 = max(y0, math.floor(y - r - pad)), min(y1, math.ceil(y + r + pad) + 1)
        if bx1 <= bx0 or by1 <= by0:
            continue
        d = np.hypot(np.arange(bx0, bx1)[None, :] - x, np.arange(by0, by1)[:, None] - y)
        sub = order[by0 - y0:by1 - y0, bx0 - x0:bx1 - x0]
        np.minimum(sub, (t + np.maximum(d - r, 0.0)).astype(np.float32), out=sub)
    order[np.isinf(order)] = L[-1]
    out = (order, step, float(L[-1]))
    with _LOCK:
        _ORDERS[key] = out
        while len(_ORDERS) > 8:
            _ORDERS.popitem(last=False)
    return out


def _premul(u8: np.ndarray) -> np.ndarray:
    px = u8.astype(np.float32) / 255
    return np.concatenate([px[..., :3] * px[..., 3:], px[..., 3:]], -1)


def _straight8(px: np.ndarray) -> np.ndarray:
    a = px[..., 3:]
    rgb = np.where(a > 0, px[..., :3] / np.maximum(a, 1e-8), 0.0)
    return np.clip(np.rint(np.concatenate([rgb, a], -1) * 255), 0, 255).astype(np.uint8)


def pixels(frame: dict, w: int, h: int, amount: float) -> np.ndarray:
    """The drawing at `amount` (0..1) drawn so far, as HxWx4 uint8 straight alpha (shared with the kit's memo at 0 / 1 and
    between marks: copy before changing it)."""
    got = marks(frame)
    k, f = cut(frame, amount)
    if k >= len(got):
        return canvas.rgba8(frame, w, h)
    before = canvas.rgba8(_prefix(frame, k), w, h)
    if f <= 0:
        return before
    after = canvas.rgba8(_prefix(frame, k + 1), w, h)
    changed = (before != after).any(-1)
    cols, rows = np.flatnonzero(changed.any(0)), np.flatnonzero(changed.any(1))
    if not len(cols):
        return before
    box = (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1)
    li, si, _ = got[k]
    s = frame["paints"][li]["strokes"][si]
    if s.get("type") == "stroke":
        order, step, length = _order(s, box)
        shown = np.clip((f * length - order) / step + 1, 0.0, 1.0)
    else:                               # a fill fades in over its share
        shown = np.full((box[3] - box[1], box[2] - box[0]), f, np.float32)
    x0, y0, x1, y1 = box
    a, b = _premul(before[y0:y1, x0:x1]), _premul(after[y0:y1, x0:x1])
    out = before.copy()
    out[y0:y1, x0:x1] = _straight8(a + (b - a) * shown[..., None])
    return out


def _key(frame: dict, w: int, h: int, amount: float, cropped: bool) -> str:
    return cache_key("paint.drawn", f"{VERSION}.{canvas.ENGINE_VERSION}", [canvas.content_key(frame, w, h)],
                     {"w": w, "h": h, "amount": amount, "crop": cropped})


def _entry(key: str, cropped: bool) -> dict:
    folder = CACHE.path("paint", key)
    if not cropped:
        return {"src": str(folder / "canvas.png")}
    crop = json.loads((folder / "crop.json").read_text(encoding="utf-8"))["crop"]
    return {"src": str(folder / "ink.png"), **({"crop": crop} if crop else {})}


def made(frame: dict, w: int, h: int, amount: float, cropped: bool) -> dict | None:
    """The frame entry ({"src", "crop"?}) of the drawing at `amount` if its picture is made (cheap), else None."""
    key = _key(frame, w, h, amount, cropped)
    return _entry(key, cropped) if CACHE.get("paint", key) else None


def png(frame: dict, w: int, h: int, amount: float, cropped: bool) -> dict:
    """The drawing at `amount` as the engine's frame entry: `cropped` (a drawing layer) holds only its ink with `crop`
    (ink.py's rule), else the whole canvas (paint on an element). Made once, then only read."""
    key = _key(frame, w, h, amount, cropped)
    if CACHE.get("paint", key):
        return _entry(key, cropped)
    from PIL import Image

    def make(tmp):
        u8 = pixels(frame, w, h, amount)
        if not cropped:
            Image.fromarray(np.ascontiguousarray(u8), "RGBA").save(tmp / "canvas.png", compress_level=1)
            return
        crop = ink.bounds(u8[..., 3])
        part = u8[crop[1]:crop[1] + crop[3], crop[0]:crop[0] + crop[2]] if crop else np.zeros((1, 1, 4), np.uint8)
        Image.fromarray(np.ascontiguousarray(part), "RGBA").save(tmp / "ink.png", compress_level=1)
        (tmp / "crop.json").write_text(json.dumps({"crop": crop}), encoding="utf-8")
    CACHE.put("paint", key, make, {"w": w, "h": h, "amount": amount, "content": canvas.content_key(frame, w, h)})
    return _entry(key, cropped)


def _part(frame: dict, size: tuple, amount: float, cropped: bool, later: list | None) -> dict:
    """One picture of the drawing part drawn: made now, or (a screen: `later`) made off its thread, nothing meanwhile."""
    w, h = size
    if amount <= 0:
        return ({"src": str(ink.png({"paints": []}, w, h)[0])} if cropped else {"src": str(canvas.png({"paints": []}, w, h))})
    got = made(frame, w, h, amount, cropped)
    if got is not None:
        return got
    if later is None:
        return png(frame, w, h, amount, cropped)
    later.append(lambda: png(frame, w, h, amount, cropped))
    return _part(frame, size, 0.0, cropped, None)


def entries(item: dict, run: list, fps: float, first: int, last: int, size: tuple, full, later: list | None) -> list[dict]:
    """The layer's frame entries ({"at", "src", "crop"?}) with Drawn so far applied. `run`: [(frame number, drawing)]
    sorted (drawing.repeats / within), `first`..`last`: the frames to cover, `full(drawing)`: its entry when whole.
    Unkeyed: each drawing as it is drawn so far. Keyed: an entry at each frame where what shows changes."""
    from rostrum_core.keys import keys_of
    cropped = item["type"] == "drawing"
    if not keys_of(item, DRAWN):
        a = amount_at(item, 0.0)
        return [{"at": n, **(full(f) if a >= 1 else _part(f, size, a, cropped, later))} for n, f in run]
    out, i, shown = [], 0, None
    for n in range(max(first, run[0][0]) if run else 0, last + 1 if run else 0):
        while i + 1 < len(run) and run[i + 1][0] <= n:
            i += 1
        a = amount_at(item, n / fps)
        if (i, a) != shown:
            shown, f = (i, a), run[i][1]
            out.append({"at": n, **(full(f) if a >= 1 else _part(f, size, a, cropped, later))})
    return out or [{"at": n, **full(f)} for n, f in run[:1]]
