"""Where the pixels are made: a canvas item (its paint layers' strokes) -> pixels. The strokes in the document are
the truth; pixels are only ever a cache of them, and a look never replays from scratch.

Each paint layer's state after its first i strokes has a **chain key** (the key after i-1 strokes + stroke i's
JSON + what it reads: its mask, and the layers below when it picks them up). A render finds the longest prefix it
already holds and stamps only the strokes after it: a new stroke costs one stroke, undo / redo / a redrawn frame
cost the strokes after the nearest kept state. Kept states live in memory (LRU, `BUDGET` bytes); finished canvases
are PNG files keyed by their content (`png`), which is all the 2D engine reads. Keys include `ENGINE_VERSION`
(a hash of the brush code), so a brush change never serves stale pixels.
"""
from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import brush, compose, marks

CACHE_DIR = Path.home() / ".rostrum" / "cache" / "paint"
PNG_BYTES = 1 << 30              # size of CACHE_DIR before the oldest pictures go
BUDGET = 1200 << 20              # bytes of kept layer states in memory
CHECKPOINT = 24                  # during a long replay, keep a state every N strokes
_HERE = Path(__file__).resolve().parent
ENGINE_VERSION = hashlib.sha1(b"".join((_HERE / f).read_bytes() for f in ("marks.py", "brush.py", "canvas.py",
                                                                           "compose.py"))).hexdigest()[:12]


@dataclass
class Pixels:
    rgba: np.ndarray             # HxWx4 float32, premultiplied sRGB 0..1, transparent where unpainted
    top: np.ndarray              # HxW int32: index into `order` of the last stroke that painted there, -1 = none
    order: list                  # stroke ids, bottom layer first, painting order


class _Kept:
    """LRU of layer states: chain key -> (pixels HxWx4 float32, top HxW int32 local stroke index)."""

    def __init__(self, budget):
        self.budget, self.items, self.bytes = budget, OrderedDict(), 0

    def get(self, key):
        if key in self.items:
            self.items.move_to_end(key)
            return self.items[key]
        return None

    def put(self, key, px, top):
        if key in self.items:
            return
        self.items[key] = (px, top)
        self.bytes += px.nbytes + top.nbytes
        while self.bytes > self.budget and len(self.items) > 1:
            _, (a, b) = self.items.popitem(last=False)
            self.bytes -= a.nbytes + b.nbytes


KEPT = _Kept(BUDGET)
_PAPER: dict = {}


def _h(*parts) -> str:
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()


def _paper(w, h):
    if (w, h) not in _PAPER:
        _PAPER.clear()
        _PAPER[(w, h)] = marks.Paper(h, w, 0, 3.0)
    return _PAPER[(w, h)]


def stamp(layer_px, s: dict, w, h, masks: dict, under=None):
    """Paint one stroke item into a layer (in place); its Coverage or None. The one place a stroke item becomes
    brush-engine arguments."""
    rgb = [int(s["color"][i:i + 2], 16) / 255 for i in (1, 3, 5)]
    params = dict(opacity=s["opacity"], hardness=s["hardness"], spacing=s["spacing"], jitter=s["jitter"],
                  seed=s["seed"], angle=None if s["follow"] else s["angle"], grain=s["grain"], mode=s["mode"],
                  color_jitter=s["color_jitter"], hue_jitter=s["hue_jitter"], size_pressure=s["size_pressure"],
                  opacity_pressure=s["opacity_pressure"], wet=s["wet"] if s["smudge"] else 0.0,
                  sample_all=bool(s["smudge"] and s["pickup"]))
    mask = compose.mask_array(masks[s["mask"]], w, h) if s.get("mask") else None
    return brush.stamp_stroke(layer_px, s["points"], rgb, s["size"], s["brush"], mask=mask,
                              under=under if params["sample_all"] else None, paper=_paper(w, h), **params)


def _chain(paint, w, h, masks, below_key) -> list[str]:
    keys = [_h(ENGINE_VERSION, str(w), str(h))]
    for s in paint["strokes"]:
        reads = json.dumps(masks.get(s.get("mask")), sort_keys=True) if s.get("mask") else ""
        if s.get("smudge") and s.get("pickup"):
            reads += below_key
        keys.append(_h(keys[-1], json.dumps(s, sort_keys=True), reads))
    return keys


def _layer(paint, w, h, masks, below_key, under_fn):
    """(pixels, top, end key) of one paint layer, from the longest kept prefix. Returned arrays are shared: copy
    before changing them."""
    keys = _chain(paint, w, h, masks, below_key)
    n = len(keys) - 1
    start = next(i for i in range(n, -1, -1) if i == 0 or KEPT.get(keys[i]) is not None)
    got = KEPT.get(keys[start])
    if start == n and got is not None:
        return got[0], got[1], keys[n]
    px = got[0].copy() if got else np.zeros((h, w, 4), np.float32)
    top = got[1].copy() if got else np.full((h, w), -1, np.int32)
    for i in range(start, n):
        s = paint["strokes"][i]
        cov = stamp(px, s, w, h, masks, under_fn() if s.get("smudge") and s.get("pickup") else None)
        if cov is not None:
            x0, y0, x1, y1 = cov.bbox
            top[y0:y1, x0:x1][cov.a > 1 / 255] = i
        if (i + 1) % CHECKPOINT == 0 and i + 1 < n:
            KEPT.put(keys[i + 1], px.copy(), top.copy())
    KEPT.put(keys[n], px, top)
    return px, top, keys[n]


def _layers(canvas, w, h):
    """[(paint item, pixels, top, key)] bottom first, and the canvas's content key."""
    masks = {m["id"]: m for m in canvas.get("paintmasks", [])}
    out, below = [], _h("below")
    for paint in canvas.get("paints", []):
        done = list(out)
        px, top, key = _layer(paint, w, h, masks, below,
                              lambda done=done: compose.over([(p, x) for p, x, _, _ in done], w, h)[..., :3])
        out.append((paint, px, top, key))
        below = _h(below, key, json.dumps({k: paint[k] for k in ("mode", "opacity", "visible")}, sort_keys=True))
    return out, below


_SEEN: OrderedDict = OrderedDict()     # content key -> (Pixels, rgba8 or None): the last few canvases looked at
SEEN_KEEP = 6


def render(canvas: dict, w: int, h: int) -> Pixels:
    key = (content_key(canvas, w, h), w, h)
    got = _SEEN.get(key)
    if got is not None and got[0] is not None:
        _SEEN.move_to_end(key)
        return got[0]
    pix = _render(canvas, w, h)
    _remember(key, pix, got[1] if got else None)
    return pix


def forget():
    """Drop every pixel kept in memory (the next render stamps from the strokes alone)."""
    KEPT.items.clear()
    KEPT.bytes = 0
    _SEEN.clear()


def _render(canvas, w, h) -> Pixels:
    layers, _ = _layers(canvas, w, h)
    rgba = compose.over([(p, px) for p, px, _, _ in layers], w, h)
    top, order = np.full((h, w), -1, np.int32), []
    for paint, _, ltop, _ in layers:
        if paint["visible"]:
            hit = ltop >= 0
            top[hit] = ltop[hit] + len(order)
        order += [s["id"] for s in paint["strokes"]]
    return Pixels(rgba, top, order)


def layer_rgba(canvas: dict, paint_id: str, w: int, h: int) -> np.ndarray:
    """One paint layer as HxWx4 uint8 straight alpha (its own pixels, ignoring its blend and visibility)."""
    for paint, px, _, _ in _layers(canvas, w, h)[0]:
        if paint["id"] == paint_id:
            return compose.straight8(px)
    raise KeyError(f"no paint layer {paint_id!r} in {canvas['id']}; it has: "
                   f"{', '.join(p['id'] for p in canvas.get('paints', []))}")


def rgba8(canvas: dict, w: int, h: int) -> np.ndarray:
    """The canvas as HxWx4 uint8 straight alpha (shared with the memo: copy before changing it). Read back from its
    content-keyed PNG when one exists (the file holds exactly these bytes), so a fresh process never restamps to look."""
    key = (content_key(canvas, w, h), w, h)
    got = _SEEN.get(key)
    if got is not None and got[1] is not None:
        return got[1]
    path = _png_path(key[0], w, h)
    if path.is_file():
        from PIL import Image
        with Image.open(path) as im:
            u8 = np.asarray(im.convert("RGBA"))
        _remember(key, got[0] if got else None, u8)
        return u8
    pix = render(canvas, w, h)
    u8 = compose.straight8(pix.rgba)
    _remember(key, pix, u8)
    return u8


def _remember(key, pix, u8):
    _SEEN[key] = (pix, u8)
    _SEEN.move_to_end(key)
    while len(_SEEN) > SEEN_KEEP:
        _SEEN.popitem(last=False)


def _png_path(key: str, w: int, h: int) -> Path:
    return CACHE_DIR / f"{key}_{w}x{h}.png"


def content_key(canvas: dict, w: int, h: int) -> str:
    """The canvas's content key from its strokes' JSON alone (no pixels), equal to what `_layers` computes."""
    masks = {m["id"]: m for m in canvas.get("paintmasks", [])}
    below = _h("below")
    for paint in canvas.get("paints", []):
        key = _chain(paint, w, h, masks, below)[-1]
        below = _h(below, key, json.dumps({k: paint[k] for k in ("mode", "opacity", "visible")}, sort_keys=True))
    return below


def png(canvas: dict, w: int, h: int) -> Path:
    """The canvas as a PNG (straight-alpha RGBA, w×h), named by its content: made once, then only read."""
    path = _png_path(content_key(canvas, w, h), w, h)
    if path.is_file():
        return path
    from PIL import Image
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".partial.png")
    Image.fromarray(rgba8(canvas, w, h), "RGBA").save(tmp, compress_level=1)
    tmp.replace(path)
    _trim()
    return path


def _trim():
    files = sorted(((p.stat().st_mtime, p.stat().st_size, p) for p in CACHE_DIR.glob("*.png")), reverse=True)
    total = 0
    for _, size, p in files:                       # newest kept first; past the cap the rest go
        total += size
        if total > PNG_BYTES:
            p.unlink(missing_ok=True)
