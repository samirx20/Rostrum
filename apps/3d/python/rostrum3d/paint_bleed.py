"""Bleed: a painted picture's colours carried a few texels past each piece's edge of the unfolded surface, so the
renderers' smooth reading of the picture (it mixes neighbouring texels) shows no line at a seam. Only texels outside
every piece are written, at most `pad(size)` of them out: half the gap the core's unfold leaves between pieces
(core unfold.cpp: xatlas padding = size / 256, 2..16 px), so a piece's bleed never reaches another piece.

The pieces come from the item's own unfold: a mesh's `uvs` (one u, v per face corner, with its `faceCounts`) or a
clay's surface (clay_paint.Surface.uv). A mesh on the shape's own surface (`uvs` []) has no pieces known here: no bleed.
"""
from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict

import numpy as np

MOST_FACES = 60000                  # a surface with more pieces' triangles than this is drawn too slowly here: no bleed
_LOCK = threading.RLock()
_MASKS: OrderedDict = OrderedDict()


def pad(size: int) -> int:
    return max(1, min(16, max(2, size // 256)) // 2)


def _polygons(item: dict, surface) -> list | None:
    if surface is not None:
        return None if len(surface.uv) > MOST_FACES else list(surface.uv)
    uvs, counts = item.get("uvs") or [], item.get("faceCounts") or []
    if not uvs or not counts or len(uvs) != 2 * sum(counts) or len(counts) > MOST_FACES:
        return None
    flat, out, at = np.asarray(uvs, np.float64).reshape(-1, 2), [], 0
    for c in counts:
        out.append(flat[at:at + c])
        at += c
    return out


def key(item: dict, surface, size: int) -> str:
    """What the pieces depend on ("" when none are known): in a painted picture's cache key."""
    if surface is not None:
        return f"clay:{surface.key}:{size}" if len(surface.uv) <= MOST_FACES else ""
    if not item.get("uvs") or not item.get("faceCounts"):
        return ""
    h = hashlib.sha1(np.asarray(item["uvs"], np.float32).tobytes() + np.asarray(item["faceCounts"], np.int32).tobytes())
    return f"mesh:{h.hexdigest()[:16]}:{size}"


def pieces(item: dict, surface, size: int) -> np.ndarray | None:
    """(size, size) bool: texels inside a piece of the unfolded surface, or None when they aren't known."""
    k = key(item, surface, size)
    if not k:
        return None
    with _LOCK:
        if k in _MASKS:
            _MASKS.move_to_end(k)
            return _MASKS[k]
    polys = _polygons(item, surface)
    if polys is None:
        return None
    from PIL import Image, ImageDraw
    im = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(im)
    for p in polys:
        draw.polygon([(float(u) * size - 0.5, (1.0 - float(v)) * size - 0.5) for u, v in p], fill=255)
    mask = np.asarray(im) > 0
    with _LOCK:
        _MASKS[k] = mask
        while len(_MASKS) > 4:
            _MASKS.popitem(last=False)
    return mask


def bleed(img: np.ndarray, inside: np.ndarray, near: np.ndarray, size: int) -> np.ndarray:
    """`img` (size × size × c, float or uint8) with texels outside the pieces (`inside` False) within pad(size) of a piece set to
    the mean of their set neighbours, ring by ring; only round `near` (bool: where paint is, the rest is the
    material's even value already). In place, returned."""
    n = pad(size)
    ys, xs = np.nonzero(near)
    if not len(xs):
        return img
    y0, y1 = max(0, ys.min() - n - 1), min(size, ys.max() + n + 2)
    x0, x1 = max(0, xs.min() - n - 1), min(size, xs.max() + n + 2)
    v, have = img[y0:y1, x0:x1].astype(np.float32), inside[y0:y1, x0:x1].copy()
    H, W = have.shape
    for _ in range(n):
        pv, ph = np.pad(v, ((1, 1), (1, 1), (0, 0))), np.pad(have, 1)
        s, cnt = np.zeros(v.shape, np.float32), np.zeros(have.shape, np.float32)
        for dy, dx in ((0, 1), (2, 1), (1, 0), (1, 2)):
            hs = ph[dy:dy + H, dx:dx + W]
            s += pv[dy:dy + H, dx:dx + W] * hs[..., None]
            cnt += hs
        grow = ~have & (cnt > 0)
        if not grow.any():
            break
        v[grow] = s[grow] / cnt[grow][:, None]
        have |= grow
    img[y0:y1, x0:x1] = np.round(v) if img.dtype == np.uint8 else v
    return img
