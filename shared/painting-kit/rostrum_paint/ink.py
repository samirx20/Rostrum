"""A canvas's picture as only its ink: the PNG holds the rectangle where anything is painted (alpha > 0, whole px, 1 px
spare round it, inside the canvas), and `crop` [x, y, w, h] says where that rectangle sits in the canvas's w × h px.
A 6000 px sky with a few clouds costs the clouds on disk and in the engine. A canvas with no ink is a 1 × 1 see-through
PNG and no crop.

Named by the canvas's content (canvas.content_key) like `canvas.png`, in the same shared cache (kind "paint"); the
crop is written beside the picture (crop.json) and kept in memory, so `made` answers from the strokes' JSON alone,
without pixels. Drawings use this (the engine's `crop`, ENGINE_CONTRACT.md § 2); paint on an element and painted fills
keep the whole canvas (`canvas.png`).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import numpy as np

from rostrum_core.cache import CACHE, cache_key

from . import canvas

PAD = 1                                  # px of nothing kept round the ink (the engine's smoothing never clips it)
_CROPS: dict = {}                        # cache key -> crop (or None): read once per process
_LOCK = threading.Lock()


def bounds(alpha: np.ndarray, pad: int = PAD) -> list[int] | None:
    """[x, y, w, h] of the pixels with alpha > 0, `pad` px wider each way inside the canvas; None when there are none."""
    cols, rows = np.flatnonzero(alpha.any(axis=0)), np.flatnonzero(alpha.any(axis=1))
    if not len(cols):
        return None
    h, w = alpha.shape
    x0, y0 = max(0, int(cols[0]) - pad), max(0, int(rows[0]) - pad)
    x1, y1 = min(w, int(cols[-1]) + 1 + pad), min(h, int(rows[-1]) + 1 + pad)
    return [x0, y0, x1 - x0, y1 - y0]


def _key(c: dict, w: int, h: int) -> str:
    return cache_key("paint.ink", f"rostrum-paint-ink@{canvas.ENGINE_VERSION}.1", [canvas.content_key(c, w, h)],
                     {"w": w, "h": h, "pad": PAD})


def _entry(key: str) -> tuple[Path, list[int] | None]:
    folder = CACHE.path("paint", key)
    with _LOCK:
        if key not in _CROPS:
            _CROPS[key] = json.loads((folder / "crop.json").read_text(encoding="utf-8"))["crop"]
            if len(_CROPS) > 4096:
                _CROPS.clear()
        return folder / "ink.png", _CROPS.get(key)


def made(c: dict, w: int, h: int) -> tuple[Path, list[int] | None] | None:
    """(the ink's PNG, its crop) if made already (cheap: no pixels), else None: `png` makes it."""
    key = _key(c, w, h)
    return _entry(key) if CACHE.get("paint", key) else None


def png(c: dict, w: int, h: int) -> tuple[Path, list[int] | None]:
    """(the canvas's ink as a PNG, straight-alpha RGBA; its crop [x, y, w, h] in canvas px, None when there is no
    ink): made once, then only read."""
    key = _key(c, w, h)
    if CACHE.get("paint", key):
        return _entry(key)
    from PIL import Image

    def make(tmp: Path):
        u8 = canvas.rgba8(c, w, h)
        crop = bounds(u8[..., 3])
        part = u8[crop[1]:crop[1] + crop[3], crop[0]:crop[0] + crop[2]] if crop else np.zeros((1, 1, 4), np.uint8)
        Image.fromarray(np.ascontiguousarray(part), "RGBA").save(tmp / "ink.png", compress_level=1)
        (tmp / "crop.json").write_text(json.dumps({"crop": crop}), encoding="utf-8")
    CACHE.put("paint", key, make, {"w": w, "h": h, "content": canvas.content_key(c, w, h)})
    return _entry(key)
