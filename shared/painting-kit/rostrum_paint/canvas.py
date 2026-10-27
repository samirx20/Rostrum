"""Where the pixels are made: a canvas item (its paint layers' strokes) -> pixels. The strokes in the document are
the truth; pixels are only ever a cache of them, and a look never replays from scratch.

Each paint layer's state after its first i strokes has a **chain key** (the key after i-1 strokes + stroke i's
JSON + what it reads: its mask, and the layers below when it picks them up). A render finds the longest prefix it
already holds and stamps only the strokes after it: a new stroke costs one stroke, undo / redo / a redrawn frame
cost the strokes after the nearest kept state; a drawing that grew (its strokes moved by whole px, the paper with them)
keeps its kept states, moved (`_grown_from`), and a render already running on another thread is waited for, not
stamped twice (`render`). Kept states live in memory (LRU, `BUDGET` bytes); finished canvases
are PNG files in the shared cache (rostrum_core.cache, kind "paint"), keyed by their content (`png`), which is all
the 2D engine reads. Keys include `ENGINE_VERSION`
(a hash of the brush code), so a brush change never serves stale pixels.

Thread-safe: a screen makes pictures on a worker thread while its own thread reads others (`_LOCK` guards the kept
states and memos; the pixels themselves are never changed once kept). A layer's chain keys are remembered with the
strokes they were made from (`_CHAINS`), so after a new stroke only that stroke is keyed: a document never changes a
stroke in place, so the same stroke objects in the same order are the same keys.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from rostrum_core.cache import CACHE, cache_key

from . import brush, compose, fill, marks, native, shape

BUDGET = 1200 << 20              # bytes of kept layer states in memory
CHECKPOINT = 24                  # during a long replay, keep a state at least every N strokes ...
CHECKPOINT_COST = 8              # ... and not before the strokes since the last one took CHECKPOINT_COST times a copy of the canvas
_HERE = Path(__file__).resolve().parent
_LOCK = threading.RLock()        # the kept states, the memos and the paper: shared by a screen's threads
ENGINE_VERSION = hashlib.sha1(b"".join((_HERE / f).read_bytes() for f in ("marks.py", "brush.py", "canvas.py",
                                                                           "compose.py", "fill.py", "shape.py", "pictures.py",
                                                                           "wrap.py"))).hexdigest()[:12]


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
        with _LOCK:
            if key in self.items:
                self.items.move_to_end(key)
                return self.items[key]
            return None

    def put(self, key, px, top):
        with _LOCK:
            if key in self.items:
                return
            self.items[key] = (px, top)
            self.bytes += px.nbytes + top.nbytes
            while self.bytes > self.budget and len(self.items) > 1:
                _, (a, b) = self.items.popitem(last=False)
                self.bytes -= a.nbytes + b.nbytes


# Who lays the dabs: the 2D engine's native stamper when it is built (the same pixels as numpy, bit for bit; its
# test: tests/test_native.py), else numpy. `STAMPER` says which; when it is numpy, `slow_note` says so once.
LAY = native.lay if native.available() else None
STAMPER = "native" if LAY else "numpy"
_told = False


def status() -> dict:
    """The kit's state for screens and agents: which stamper lays the dabs, and why if it is the slow one."""
    return {"stamper": STAMPER, "note": None if LAY else (
        "Brushes are running the slow way (same pixels, about 10x slower): the native stamper is not built at "
        f"{native.lib_path()}. Build it: cargo build -p rostrum2d-stamp --profile agent (in apps/2d/engine).")}


def slow_note() -> str | None:
    """The slow-brushes note the first time it is asked for in this process, else None (said once, not every reply)."""
    global _told
    if LAY or _told:
        return None
    _told = True
    return status()["note"]


KEPT = _Kept(BUDGET)
_PAPER: dict = {}


def _h(*parts) -> str:
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()


def origin(canvas: dict) -> tuple[int, int]:
    """Where the canvas's paper starts, in its px: (paperX, paperY), moved with the strokes when a drawing grows left or
    up, so the grain stays under them. (0, 0) for a canvas that never did."""
    return int(canvas.get("paperX", 0)), int(canvas.get("paperY", 0))


def _paper(w, h, picture="tooth", scale=1.0, at=(0, 0), wrap=False):
    """The canvas's paper (kept: a stroke and the next on the same paper share it). Strokes made before paper
    choice name none: the engine's tooth, at its first size. `wrap`: the paper of a seamless canvas (marks.Paper)."""
    key = (w, h, picture, scale, at, wrap)
    with _LOCK:
        if key not in _PAPER:
            if len(_PAPER) > 4:
                _PAPER.clear()
            _PAPER[key] = marks.Paper(h, w, 0, 3.0 * scale, picture, scale, at, wrap)
        return _PAPER[key]


def stamp(layer_px, s: dict, w, h, masks: dict, under=None, at=(0, 0), carry=None):
    """Paint one stroke (or fill) item into a layer (in place); its Coverage or None. The one place a stroke item
    becomes brush-engine arguments. `at`: where the paper starts (`origin`). `carry`: brush.stamp_stroke's."""
    rgb = [int(s["color"][i:i + 2], 16) / 255 for i in (1, 3, 5)]
    mask = compose.mask_array(masks[s["mask"]], w, h) if s.get("mask") else None
    if s["type"] == "fill":
        return fill.lay(layer_px, s, rgb, mask)
    params = dict(opacity=s["opacity"], hardness=s["hardness"], spacing=s["spacing"], jitter=s["jitter"],
                  seed=s["seed"], angle=None if s["follow"] else s["angle"], grain=s["grain"], mode=s["mode"],
                  color_jitter=s["color_jitter"], hue_jitter=s["hue_jitter"], size_pressure=s["size_pressure"],
                  opacity_pressure=s["opacity_pressure"], wet=s["wet"] if s["smudge"] else 0.0,
                  sample_all=bool(s["smudge"] and s["pickup"]), **{k: s.get(k, 0.0) for k in shape.KEYS},
                  even=s.get("even", False), texture=s.get("texture", "none"),   # absent: made before they were
                  wrap=bool(s.get("wrap")))     # seamless: the canvas's edges joined (wrap.py)
    paper = _paper(w, h, s.get("paper", "tooth"), s.get("paper_scale", 1.0), at, params["wrap"])
    return brush.stamp_stroke(layer_px, s["points"], rgb, s["size"], s["brush"], mask=mask,
                              under=under if params["sample_all"] else None, paper=paper, lay=LAY, carry=carry, **params)


_CHAINS: OrderedDict = OrderedDict()     # (paint id, w, h) -> (its strokes, what they read, their chain keys)
CHAINS_KEEP = 256


def _chain(paint, w, h, masks, below_key, at=(0, 0)) -> list[str]:
    strokes, mine = paint["strokes"], (paint["id"], w, h, at)
    reads_of = json.dumps([masks.get(s.get("mask")) for s in strokes if s.get("mask")], sort_keys=True) + below_key
    with _LOCK:
        got = _CHAINS.get(mine)
    keys, done = [_h(ENGINE_VERSION, str(w), str(h), *([f"{at[0]},{at[1]}"] if any(at) else []))], 0
    if got is not None and got[1] == reads_of:
        old = got[0]
        while done < min(len(old), len(strokes)) and old[done] is strokes[done]:
            done += 1
        keys = got[2][:done + 1]
    for s in strokes[done:]:
        reads = json.dumps(masks.get(s.get("mask")), sort_keys=True) if s.get("mask") else ""
        if s.get("smudge") and s.get("pickup"):
            reads += below_key
        keys.append(_h(keys[-1], json.dumps(s, sort_keys=True), reads))
    with _LOCK:
        _CHAINS[mine] = (list(strokes), reads_of, keys)
        _CHAINS.move_to_end(mine)
        while len(_CHAINS) > CHAINS_KEEP:
            _CHAINS.popitem(last=False)
    return keys


MOVED_PX = 0.006                 # a grown drawing's points are moved and rounded to 0.01 px (paint_grow.shifted)


def _moved(old: dict, new: dict, dx: int, dy: int) -> bool:
    """Whether `new` is `old` moved by whole px (dx, dy), as a drawing's growth moves its strokes, and stamps the same
    marks moved (no fill, mask, pickup of the layers below or seamless edge: those read the canvas's edges or more)."""
    if new.get("type") != "stroke" or new.get("mask") or new.get("wrap") or new.get("smudge") and new.get("pickup"):
        return False
    if len(old) != len(new) or any(old.get(k) != v for k, v in new.items() if k != "points"):
        return False
    a, b = old["points"], new["points"]
    return len(a) == len(b) and all(len(p) == len(q) and abs(p[0] + dx - q[0]) <= MOVED_PX and abs(p[1] + dy - q[1]) <= MOVED_PX
                                    and p[2:] == q[2:] for p, q in zip(a, b))


def _grown_from(paint, w, h, at, keys):
    """A kept state of this paint layer from before its drawing grew (bigger, its strokes moved right / down by whole
    px with the paper's origin), placed in the canvas it has now: (stroke count, pixels, top) or None. A drawing that
    grows at each sweep of a wash then stamps only its new stroke, not all of them again (it froze the pen's press for
    seconds: critic r12). The marks are the old ones moved; a stroke whose marks read the canvas's edges is stamped
    again (`_moved`)."""
    strokes = paint["strokes"]
    with _LOCK:
        olds = [(k, v) for k, v in _CHAINS.items() if k[0] == paint["id"] and k[1:] != (w, h, at)]
    best = None
    for (_, ow, oh, oat), (old, _, okeys) in reversed(olds):
        dx, dy = at[0] - oat[0], at[1] - oat[1]
        if dx < 0 or dy < 0 or ow + dx > w or oh + dy > h:
            continue
        same = 0
        while same < min(len(old), len(strokes)) and _moved(old[same], strokes[same], dx, dy):
            same += 1
        kept = next((i for i in range(same, 0, -1) if KEPT.get(okeys[i]) is not None), 0)
        if kept and (best is None or kept > best[0]):
            best = (kept, KEPT.get(okeys[kept]), dx, dy, ow, oh)
    if best is None or best[1] is None:
        return None
    kept, (opx, otop), dx, dy, ow, oh = best
    px, top = np.zeros((h, w, 4), np.float32), np.full((h, w), -1, np.int32)
    px[dy:dy + oh, dx:dx + ow], top[dy:dy + oh, dx:dx + ow] = opx, otop
    KEPT.put(keys[kept], px, top)
    return kept, px, top


def _layer(paint, w, h, masks, below_key, under_fn, at=(0, 0)):
    """(pixels, top, end key) of one paint layer, from the longest kept prefix (or one kept before the drawing grew:
    `_grown_from`). Returned arrays are shared: copy before changing them."""
    keys = _chain(paint, w, h, masks, below_key, at)
    n = len(keys) - 1
    start = next(i for i in range(n, -1, -1) if i == 0 or KEPT.get(keys[i]) is not None)
    got = KEPT.get(keys[start])
    if start == n and got is not None:
        return got[0], got[1], keys[n]
    if start == 0 and n and (grown := _grown_from(paint, w, h, at, keys)) is not None:
        start, got = grown[0], grown[1:]
        if start == n:
            return got[0], got[1], keys[n]
    px = got[0].copy() if got else np.zeros((h, w, 4), np.float32)
    top = got[1].copy() if got else np.full((h, w), -1, np.int32)
    last, copy_s, spent = start, 0.0, 0.0       # the stroke a state was last kept at; what a copy of this canvas costs; stamping since
    for i in range(start, n):
        s = paint["strokes"][i]
        t0 = time.perf_counter()
        cov = stamp(px, s, w, h, masks, under_fn() if s.get("smudge") and s.get("pickup") else None, at)
        if cov is not None:
            x0, y0, x1, y1 = cov.bbox
            top[y0:y1, x0:x1][cov.a > 1 / 255] = i
        spent += time.perf_counter() - t0
        # A kept state is a copy of the whole canvas, so on a big canvas a copy every 24 strokes cost more than the strokes
        # (a 5200 x 1300 grass layer: 25 s of a 68 s first look) and the memory budget held only the last few anyway.
        # So one is kept when the strokes since the last cost CHECKPOINT_COST copies, which undo / redo then replay at most.
        if i + 1 - last >= CHECKPOINT and i + 1 < n and spent >= CHECKPOINT_COST * copy_s:
            t0 = time.perf_counter()
            KEPT.put(keys[i + 1], px.copy(), top.copy())
            copy_s, spent, last = time.perf_counter() - t0, 0.0, i + 1
    KEPT.put(keys[n], px, top)
    return px, top, keys[n]


def _layers(canvas, w, h):
    """[(paint item, pixels, top, key)] bottom first, and the canvas's content key."""
    masks = {m["id"]: m for m in canvas.get("paintmasks", [])}
    out, below = [], _h("below")
    for paint in canvas.get("paints", []):
        done = list(out)
        px, top, key = _layer(paint, w, h, masks, below,
                              lambda done=done: compose.over([(p, x) for p, x, _, _ in done], w, h)[..., :3], origin(canvas))
        out.append((paint, px, top, key))
        below = _h(below, key, json.dumps({k: paint[k] for k in ("mode", "opacity", "visible")}, sort_keys=True))
    return out, below


_SEEN: OrderedDict = OrderedDict()     # content key -> (Pixels, rgba8 or None): the last few canvases looked at
SEEN_KEEP = 6


_MAKING: dict = {}                     # content key -> threading.Event: a render running on some thread


def render(canvas: dict, w: int, h: int) -> Pixels:
    """The canvas's pixels (shared: never change them). Asked on two threads at once (a screen's picture job and a
    smudge's press), the second waits for the first's pixels instead of stamping the same strokes again."""
    key = (content_key(canvas, w, h), w, h)
    while True:
        got = _seen(key)
        if got is not None and got[0] is not None:
            return got[0]
        with _LOCK:
            making = _MAKING.get(key)
            if making is None:
                _MAKING[key] = threading.Event()
        if making is None:
            break
        making.wait()
    try:
        pix = _render(canvas, w, h)
        _remember(key, pix, got[1] if got else None)
    finally:
        with _LOCK:
            _MAKING.pop(key).set()
    return pix


def forget():
    """Drop every pixel kept in memory (the next render stamps from the strokes alone)."""
    with _LOCK:
        KEPT.items.clear()
        KEPT.bytes = 0
        _SEEN.clear()
        _CHAINS.clear()


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
    got = _seen(key)
    if got is not None and got[1] is not None:
        return got[1]
    path = _png_path(key[0], w, h)
    if CACHE.get("paint", _png_key(key[0], w, h)):
        from PIL import Image
        with Image.open(path) as im:
            u8 = np.asarray(im.convert("RGBA"))
        _remember(key, got[0] if got else None, u8)
        return u8
    pix = render(canvas, w, h)
    u8 = compose.straight8(pix.rgba)
    _remember(key, pix, u8)
    return u8


def _seen(key):
    with _LOCK:
        got = _SEEN.get(key)
        if got is not None:
            _SEEN.move_to_end(key)
        return got


def _remember(key, pix, u8):
    with _LOCK:
        _SEEN[key] = (pix, u8)
        _SEEN.move_to_end(key)
        while len(_SEEN) > SEEN_KEEP:
            _SEEN.popitem(last=False)


def _png_key(key: str, w: int, h: int) -> str:
    return cache_key("paint.canvas", f"rostrum-paint@{ENGINE_VERSION}", [key], {"w": w, "h": h})


def _png_path(key: str, w: int, h: int) -> Path:
    return CACHE.path("paint", _png_key(key, w, h)) / "canvas.png"


def _layer_keys(canvas: dict, w: int, h: int):
    """(paint layer, its pixels' key, the key of everything up to it) bottom first, from the strokes' JSON alone."""
    masks = {m["id"]: m for m in canvas.get("paintmasks", [])}
    below = _h("below")
    for paint in canvas.get("paints", []):
        key = _chain(paint, w, h, masks, below, origin(canvas))[-1]
        below = _h(below, key, json.dumps({k: paint[k] for k in ("mode", "opacity", "visible")}, sort_keys=True))
        yield paint, key, below


def content_key(canvas: dict, w: int, h: int) -> str:
    """The canvas's content key from its strokes' JSON alone (no pixels), equal to what `_layers` computes."""
    below = _h("below")
    for _, _, below in _layer_keys(canvas, w, h):
        pass
    return below


def layer_key(canvas: dict, paint_id: str, w: int, h: int) -> str:
    """One paint layer's pixels' key (what `layer_rgba` draws), cheap: from the strokes' JSON."""
    for paint, key, _ in _layer_keys(canvas, w, h):
        if paint["id"] == paint_id:
            return key
    raise KeyError(f"no paint layer {paint_id!r} in {canvas['id']}")


def made(canvas: dict, w: int, h: int) -> Path | None:
    """The canvas's PNG if it is made already (cheap: no pixels), else None: `png` makes it."""
    key = content_key(canvas, w, h)
    return _png_path(key, w, h) if CACHE.get("paint", _png_key(key, w, h)) else None


def png(canvas: dict, w: int, h: int) -> Path:
    """The canvas as a PNG (straight-alpha RGBA, w×h), named by its content: made once, then only read."""
    key = content_key(canvas, w, h)
    if CACHE.get("paint", _png_key(key, w, h)):
        return _png_path(key, w, h)
    from PIL import Image

    def make(tmp: Path):
        Image.fromarray(rgba8(canvas, w, h), "RGBA").save(tmp / "canvas.png", compress_level=1)
    return CACHE.put("paint", _png_key(key, w, h), make, {"w": w, "h": h, "content": key}) / "canvas.png"
