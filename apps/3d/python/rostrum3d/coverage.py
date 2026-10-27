"""Coverage (brief 21): how much of what a shot's camera sees is painted, per item, and the tint that shows the rest.

Both read the shot camera's texel picture (texels.py: which item and texel each pixel shows). `measure` counts, per
painted item, the pixels showing it (`seen`) and those whose texel holds paint (`painted`: any visible layer's paint
at alpha ≥ 0.5, the `alpha.png` paint_scene writes beside each painted picture), and their share (`percent`). The
**tint** marks the texels the camera sees and nothing paints with a faint orange diagonal hatch, in the item's colour
picture (UV space, so it sits on the surface in any view). It is for the screen only (`for_screen`): never in a render
or an export, which compile their own scene.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from rostrum_core.cache import CACHE, cache_key

from . import paint_scene
from .paint_fields import CHANNELS

VERSION = "rostrum3d-coverage@1"
PAINTED = 0.5                       # alpha at or over this counts as painted
ORANGE = np.array([1.0, 0.55, 0.12], np.float32)
LINE, GAP, PERIOD = 0.42, 0.12, 14  # the hatch: lines PERIOD/3 texels wide at LINE, the gaps at GAP
REQ = ("camera", "frame", "width", "height")


def _alpha01(a) -> np.ndarray:
    a = np.asarray(a)
    if a.ndim == 3:
        a = a[..., 3] if a.shape[2] == 4 else a[..., 0]
    return a.astype(np.float32) / 255 if a.dtype == np.uint8 else a.astype(np.float32)


def _texels(pic, item_id: str, size: int):
    """(the item's pixel mask, their texels' x, y in a size × size canvas)."""
    on = pic.of(item_id) & np.isfinite(pic.uv[..., 0])
    uv = pic.uv[on]
    tx = np.clip((uv[:, 0] * size).astype(int), 0, size - 1)
    ty = np.clip(((1.0 - uv[:, 1]) * size).astype(int), 0, size - 1)
    return on, tx, ty


def measure(pic, items: dict) -> dict:
    """{id: {"seen": px, "painted": px, "percent": %}} for each of `items` ({id: its painted alpha as a canvas array:
    h × w 0..1 or uint8, or RGBA}). seen: the camera's pixels showing it; painted: those on a painted texel."""
    out = {}
    for item_id, a in items.items():
        a = _alpha01(a)
        on, tx, ty = _texels(pic, item_id, a.shape[0])
        seen = int(on.sum())
        painted = int((a[ty, tx] >= PAINTED).sum()) if seen else 0
        out[item_id] = {"seen": seen, "painted": painted, "percent": round(100.0 * painted / seen, 1) if seen else 0.0}
    return out


def seen_texels(pic, item_id: str, size: int) -> np.ndarray:
    """(size, size) bool: the texels the camera sees on the item, small gaps between its pixels closed."""
    _, tx, ty = _texels(pic, item_id, size)
    m = np.zeros((size, size), bool)
    m[ty, tx] = True
    for _ in range(2):                                  # a texel with seen ones on 3+ of its 8 sides: seen too
        p = np.pad(m, 1)
        n = sum(p[dy:dy + size, dx:dx + size].astype(np.int8) for dy in range(3) for dx in range(3)) - m
        m = m | (n >= 3)
    return m


def tint(colour: np.ndarray, seen: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """`colour` (size × size × 3, 0..1) with the hatch where `seen` and not painted (alpha < PAINTED)."""
    size = colour.shape[0]
    y, x = np.mgrid[0:size, 0:size]
    line = ((x + y) % PERIOD) < PERIOD // 3
    k = np.where(line, LINE, GAP)[..., None] * (seen & (_alpha01(alpha) < PAINTED))[..., None]
    return colour * (1 - k) + ORANGE * k


def _alpha_of(props: dict) -> np.ndarray | None:
    """The item's painted alpha: the most of its painted pictures' `alpha.png` (None: no painted picture)."""
    from PIL import Image
    out = None
    for channel in CHANNELS.values():
        f = props.get(channel[1])
        side = Path(f).with_name("alpha.png") if f else None
        if side is not None and side.is_file():
            with Image.open(side) as im:
                a = np.asarray(im.convert("L"))
            out = a if out is None else np.maximum(out, a)
    return out


def _linear_to_srgb(c):
    c = np.clip(np.asarray(c, np.float32), 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def _tinted(props: dict, size: int, pic, item_id: str, alpha: np.ndarray, pic_key: str) -> str:
    """The item's colour picture with the tint, as a content-keyed PNG (made once per paint and shot view)."""
    from PIL import Image
    base = props.get("baseColorTexture") or ""
    painted = [str(props.get(c[1], "")) for c in CHANNELS.values()]          # the alpha comes from these
    key = cache_key("paint.coverage", VERSION, [base or str(props.get("baseColor")), *painted, pic_key, item_id],
                    {"size": size})
    if CACHE.get("paint", key):
        return str(CACHE.path("paint", key) / "tint.png")

    def make(tmp: Path):
        if base:
            with Image.open(base) as im:
                colour = np.asarray(im.convert("RGB").resize((size, size)), np.float32) / 255
        else:
            colour = np.broadcast_to(_linear_to_srgb(props.get("baseColor", [0.8, 0.8, 0.8])[:3]), (size, size, 3))
        out = tint(colour, seen_texels(pic, item_id, size), alpha)
        Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").save(tmp / "tint.png", compress_level=1)
    return str(CACHE.put("paint", key, make, {"item": item_id}) / "tint.png")


def for_screen(scene: dict, data: dict, shot_info: dict, texels_fn) -> tuple[dict, dict]:
    """({item: percent painted of what the shot's camera sees}, a copy of `scene` with the tint on those items) for the
    screen's coverage toggle. `shot_info`: {camera, frame, width, height}; `texels_fn(req) -> reply`: the engine's
    texels request (Engine.texels_reply / ItemEngine.texels_reply) holding `scene`. Items whose paint still waits
    (paintLater) are left out; send the finished scene."""
    from . import texels
    req = {k: shot_info[k] for k in REQ if k in shot_info}
    pic = texels.cached(paint_scene.geometry_scene(scene), req, texels_fn)
    pic_key = cache_key("texels.seen", VERSION, [texels.geometry_key(paint_scene.geometry_scene(scene))], req)
    out = {**scene, "materials": list(scene["materials"])}
    mats = {m["id"]: i for i, m in enumerate(out["materials"])}
    nodes = paint_scene._nodes(scene["items"], {})
    percent = {}
    for item in paint_scene.canvases(data.get("items", [])):
        node = nodes.get(item["id"])
        mid = f'{item["id"]}__paint'
        if node is None or mid not in mats:
            continue
        props = out["materials"][mats[mid]]["props"]
        size = int(item.get("paintSize", 2048))
        alpha = _alpha_of(props)
        alpha = np.zeros((size, size), np.uint8) if alpha is None else alpha
        percent[item["id"]] = measure(pic, {item["id"]: alpha})[item["id"]]["percent"]
        if not pic.of(item["id"]).any():
            continue
        tinted = _tinted(props, alpha.shape[0], pic, item["id"], alpha, pic_key)
        new = {**out["materials"][mats[mid]], "props": {**props, "baseColorTexture": tinted}}
        out["materials"][mats[mid]] = new
    return percent, out
