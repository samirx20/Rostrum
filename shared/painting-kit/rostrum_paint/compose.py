"""Putting paint layers together, and paint masks as pixels. Premultiplied sRGB float32 throughout; transparent
where nothing is painted (a drawing sits over whatever is under it in the host app)."""
from __future__ import annotations

from functools import lru_cache
import json
import math

import numpy as np


def over(layers, w, h) -> np.ndarray:
    """[(paint item, HxWx4 premultiplied)] bottom first -> HxWx4 premultiplied. Blends are the W3C separable ones
    (normal, multiply, screen) and a clamped add; a layer's opacity scales it; hidden layers are skipped. One
    plain layer (normal, full opacity: most drawings) is itself, clamped as a blend would: the same numbers, no blending."""
    shown = [(p, px) for p, px in layers if p["visible"] and p["opacity"] > 0]
    if len(shown) == 1 and shown[0][0]["mode"] == "normal" and shown[0][0]["opacity"] >= 1:
        out = shown[0][1].copy()
        np.minimum(out[..., :3], out[..., 3:], out=out[..., :3])
        return out
    out = np.zeros((h, w, 4), np.float32)
    for paint, px in layers:
        if paint["visible"] and paint["opacity"] > 0:
            blend(out, paint, px)
    return out


def bounds(px: np.ndarray) -> tuple[int, int, int, int] | None:
    """(y0, y1, x0, x1) of the pixels with any paint (alpha > 0: premultiplied colour is never more than its alpha),
    None when there are none."""
    seen = px[..., 3] > 0
    rows, cols = np.flatnonzero(seen.any(axis=1)), np.flatnonzero(seen.any(axis=0))
    if not len(rows):
        return None
    return int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1


def blend(out: np.ndarray, paint: dict, px: np.ndarray, box=None) -> None:
    """One visible layer onto `out` (HxWx4 premultiplied, clamped: every colour at most its alpha), in place. `box`:
    (y0, y1, x0, x1), where the layer has paint (`bounds`); outside it a see-through layer leaves `out` as it is in
    every mode (the same numbers), so only the box is worked out: a 2100 x 1080 drawing of five layers took ~1.1 s a
    picture, each Drawn so far frame of a wash."""
    if box is None:
        box = (0, px.shape[0], 0, px.shape[1])
    y0, y1, x0, x1 = box
    if y1 <= y0 or x1 <= x0:
        return
    px, region = px[y0:y1, x0:x1], out[y0:y1, x0:x1]
    s = px * np.float32(paint["opacity"]) if paint["opacity"] < 1 else px
    sa, ba = s[..., 3:], region[..., 3:]
    mode = paint["mode"]
    if mode == "normal":
        rgb = s[..., :3] + region[..., :3] * (1 - sa)
    elif mode == "multiply":
        rgb = s[..., :3] * (1 - ba) + region[..., :3] * (1 - sa) + s[..., :3] * region[..., :3]
    elif mode == "screen":
        rgb = s[..., :3] + region[..., :3] - s[..., :3] * region[..., :3]
    elif mode == "add":
        rgb = s[..., :3] + region[..., :3]
    else:
        raise ValueError(f"paint layer {paint['id']}: unknown blend {mode!r}")
    a = sa + ba - sa * ba
    if mode == "add":       # light sums; where it is brighter than the coverage, the alpha grows to carry it
        rgb = np.minimum(rgb, 1)
        a = np.maximum(a, rgb.max(axis=2, keepdims=True))
    region[..., :3] = np.minimum(rgb, a)
    region[..., 3:] = a


def straight8(px: np.ndarray) -> np.ndarray:
    """Premultiplied float -> straight-alpha RGBA uint8 (what PNGs and the engine read). Only the painted box is
    worked out (nothing painted is 0 everywhere), in place, in the same steps and precision as ever."""
    out = np.zeros(px.shape, np.uint8)
    seen = px[..., 3] > 0
    rows, cols = np.flatnonzero(seen.any(axis=1)), np.flatnonzero(seen.any(axis=0))
    if not len(rows):
        return out
    y0, y1, x0, x1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1
    part = px[y0:y1, x0:x1]
    a = part[..., 3:]
    f = np.empty(part.shape, np.float32)
    np.divide(part[..., :3], np.maximum(a, 1e-6), out=f[..., :3])
    f[..., :3][np.broadcast_to(a <= 1e-6, a.shape[:2] + (3,))] = 0
    f[..., 3:] = a
    np.clip(f, 0, 1, out=f)
    f *= 255
    f += 0.5
    out[y0:y1, x0:x1] = f
    return out


def mask_array(mask: dict, w: int, h: int) -> np.ndarray:
    """A paint mask item -> HxW float32 0..1 (antialiased polygon, feathered, inverted when asked). Cached by content."""
    return _mask(json.dumps({k: mask[k] for k in ("points", "feather", "invert")}, sort_keys=True), w, h)


def mask_box(mask: dict, w: int, h: int) -> tuple[int, int, int, int] | None:
    """(x0, y0, x1, y1) canvas px outside which `mask_array` is 0 (the whole canvas for an inverted mask; None: 0
    everywhere): a reader of one mask works only there."""
    if mask["invert"]:
        return 0, 0, w, h
    return _mask_box(mask["points"], mask["feather"], w, h)


def _mask_box(points, feather: float, w: int, h: int) -> tuple[int, int, int, int] | None:
    """(x0, y0, x1, y1) canvas px holding every px a mask's polygon and its feather can reach (None: none on the
    canvas). The blur is three box passes about `feather` px wide each, so 3 x (feather + 2) px round the shape; outside,
    the whole canvas's mask is 0 (the same bytes, test_kit)."""
    m = 3 * (math.ceil(feather) + 2) if feather else 1
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    x0, y0 = max(0, math.floor(min(xs)) - m), max(0, math.floor(min(ys)) - m)
    x1, y1 = min(w, math.ceil(max(xs)) + 1 + m), min(h, math.ceil(max(ys)) + 1 + m)
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


@lru_cache(maxsize=64)
def _mask(spec: str, w: int, h: int) -> np.ndarray:
    from PIL import Image, ImageDraw, ImageFilter
    m = json.loads(spec)
    if len(m["points"]) < 3:
        raise ValueError(f"a paint mask needs at least 3 points, it has {len(m['points'])}")
    ss, out = 4, np.zeros((h, w), np.uint8)
    box = _mask_box(m["points"], m["feather"], w, h)
    if box is not None:     # only round the shape: a window's wash drew and blurred the whole canvas at 4x (~40 ms each)
        x0, y0, x1, y1 = box
        im = Image.new("L", (x1 * ss, y1 * ss), 0)     # drawn where it sits (moved, the polygon's px came out different)
        ImageDraw.Draw(im).polygon([(x * ss, y * ss) for x, y in m["points"]], fill=255)
        im = im.crop((x0 * ss, y0 * ss, x1 * ss, y1 * ss)).reduce(ss)
        if m["feather"]:
            im = im.filter(ImageFilter.GaussianBlur(m["feather"]))
        out[y0:y1, x0:x1] = np.asarray(im)
    a = out.astype(np.float32) / 255
    a = 1 - a if m["invert"] else a
    a.setflags(write=False)
    return a
