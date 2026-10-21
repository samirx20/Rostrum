"""Putting paint layers together, and paint masks as pixels. Premultiplied sRGB float32 throughout; transparent
where nothing is painted (a drawing sits over whatever is under it in the host app)."""
from __future__ import annotations

from functools import lru_cache
import json

import numpy as np


def over(layers, w, h) -> np.ndarray:
    """[(paint item, HxWx4 premultiplied)] bottom first -> HxWx4 premultiplied. Blends are the W3C separable ones
    (normal, multiply, screen) and a clamped add; a layer's opacity scales it; hidden layers are skipped."""
    out = np.zeros((h, w, 4), np.float32)
    for paint, px in layers:
        if not paint["visible"] or paint["opacity"] <= 0:
            continue
        s = px * np.float32(paint["opacity"]) if paint["opacity"] < 1 else px
        sa, ba = s[..., 3:], out[..., 3:]
        mode = paint["mode"]
        if mode == "normal":
            rgb = s[..., :3] + out[..., :3] * (1 - sa)
        elif mode == "multiply":
            rgb = s[..., :3] * (1 - ba) + out[..., :3] * (1 - sa) + s[..., :3] * out[..., :3]
        elif mode == "screen":
            rgb = s[..., :3] + out[..., :3] - s[..., :3] * out[..., :3]
        elif mode == "add":
            rgb = s[..., :3] + out[..., :3]
        else:
            raise ValueError(f"paint layer {paint['id']}: unknown blend {mode!r}")
        a = sa + ba - sa * ba
        if mode == "add":       # light sums; where it is brighter than the coverage, the alpha grows to carry it
            rgb = np.minimum(rgb, 1)
            a = np.maximum(a, rgb.max(axis=2, keepdims=True))
        out = np.concatenate([np.minimum(rgb, a), a], axis=2)
    return out


def straight8(px: np.ndarray) -> np.ndarray:
    """Premultiplied float -> straight-alpha RGBA uint8 (what PNGs and the engine read)."""
    a = px[..., 3:]
    rgb = np.where(a > 1e-6, px[..., :3] / np.maximum(a, 1e-6), 0)
    return (np.clip(np.concatenate([rgb, a], axis=2), 0, 1) * 255 + 0.5).astype(np.uint8)


def mask_array(mask: dict, w: int, h: int) -> np.ndarray:
    """A paint mask item -> HxW float32 0..1 (antialiased polygon, feathered, inverted when asked). Cached by content."""
    return _mask(json.dumps({k: mask[k] for k in ("points", "feather", "invert")}, sort_keys=True), w, h)


@lru_cache(maxsize=64)
def _mask(spec: str, w: int, h: int) -> np.ndarray:
    from PIL import Image, ImageDraw, ImageFilter
    m = json.loads(spec)
    if len(m["points"]) < 3:
        raise ValueError(f"a paint mask needs at least 3 points, it has {len(m['points'])}")
    ss = 4
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).polygon([(x * ss, y * ss) for x, y in m["points"]], fill=255)
    im = im.reduce(ss)
    if m["feather"]:
        im = im.filter(ImageFilter.GaussianBlur(m["feather"]))
    a = np.asarray(im, np.float32) / 255
    a = 1 - a if m["invert"] else a
    a.setflags(write=False)
    return a
