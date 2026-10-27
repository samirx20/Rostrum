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

VERSION = "rostrum3d-coverage@2"
PAINTED = 0.5                       # alpha at or over this counts as painted
ORANGE = np.array([1.0, 0.55, 0.12], np.float32)
LINE, GAP = 0.45, 0.0                # the hatch: its stripes and the gaps between, how much orange
APART, WIDE = 7.0, 0.35             # stripes APART screen px apart (on the shot's picture), WIDE of that orange
UNPAINTED_SIZE = 1024               # the tint picture of an item with no paint yet
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
    """(size, size) bool: the texels the camera sees on the item, solid between its pixels (paint_view.splat's fill,
    so a surface seen at a steep angle is whole and nothing behind what hides it is)."""
    from . import paint_view
    h, w = pic.item.shape
    return paint_view.splat(pic, item_id, np.ones((h, w, 4), np.float32), size)[..., 3] > 0.5


def period(pic, item_id: str, size: int) -> int:
    """The hatch's period in texels: APART screen px of the shot's picture where the item is seen (its texels per
    screen px there, the middle of them)."""
    from . import paint_view
    cpx = paint_view._canvas(pic, size)
    on = pic.of(item_id) & np.isfinite(cpx[..., 0])
    ys, xs = np.nonzero(on)
    if not len(ys):
        return 8
    pick = np.linspace(0, len(ys) - 1, min(len(ys), 4000)).astype(int)
    scale = paint_view._scale(cpx, on, xs[pick], ys[pick])
    scale = float(np.nanmedian(scale)) if np.isfinite(scale).any() else 1.0
    return int(max(3, min(size // 4, round(APART * scale))))


def tint(colour: np.ndarray, seen: np.ndarray, alpha: np.ndarray, every: int = 8) -> np.ndarray:
    """`colour` (size × size × 3, 0..1) with the hatch where `seen` and not painted (alpha < PAINTED): diagonal
    stripes `every` texels apart."""
    size = colour.shape[0]
    y, x = np.mgrid[0:size, 0:size]
    line = ((x + y) % every) < max(1, round(every * WIDE))
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
    """The item's colour picture (its paint's, or its material's own picture or colour) with the tint, as a
    content-keyed PNG (made once per paint and shot view)."""
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
        out = tint(colour, seen_texels(pic, item_id, size), alpha, period(pic, item_id, size))
        Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").save(tmp / "tint.png", compress_level=1)
    return str(CACHE.put("paint", key, make, {"item": item_id}) / "tint.png")


def _paintable(items: list):
    """Every mesh, and every clay holding paint (an unpainted clay has no unfolded surface yet), children too."""
    for it in items:
        if it.get("type") == "mesh" or (it.get("type") == "clay" and it.get("paints")):
            yield it
        yield from _paintable(it.get("children", []))


def _copy_nodes(nodes: list) -> list:
    return [{**n, "props": dict(n.get("props", {})), **({"children": _copy_nodes(n["children"])}
                                                        if n.get("children") else {})} for n in nodes]


def _own_props(scene_mats: dict, node: dict) -> dict:
    """The props of the material the node wears in the scene, or the default material's."""
    got = scene_mats.get(node["props"].get("material", ""))
    if got is not None:
        return dict(got["props"])
    from .compile import _out
    from .material_fields import DOC_ONLY, MATERIAL
    return {p.name: _out(p, p.default) for p in MATERIAL if p.name not in DOC_ONLY}


def for_screen(scene: dict, data: dict, shot_info: dict, texels_fn) -> tuple[dict, dict]:
    """({item: percent painted of what the shot's camera sees}, a copy of `scene` with the tint on every paintable
    item the shot sees) for the screen's coverage toggle. `shot_info`: {camera, frame, width, height};
    `texels_fn(req) -> reply`: the engine's texels request (Engine.texels_reply / ItemEngine.texels_reply) holding
    `scene`. A painted item's tint goes in its `<id>__paint` material; an item with no paint yet gets `<id>__cover`, a
    copy of its own material with the tinted picture. Items whose paint still waits (paintLater) are left out; send
    the finished scene."""
    from . import texels
    req = {k: shot_info[k] for k in REQ if k in shot_info}
    pic = texels.cached(paint_scene.geometry_scene(scene), req, texels_fn)
    pic_key = cache_key("texels.seen", VERSION, [texels.geometry_key(paint_scene.geometry_scene(scene))], req)
    out = {**scene, "materials": list(scene["materials"]), "items": _copy_nodes(scene["items"])}
    by_id = {m["id"]: m for m in scene["materials"]}
    mats = {m["id"]: i for i, m in enumerate(out["materials"])}
    nodes = paint_scene._nodes(out["items"], {})
    waiting = {j["item"]["id"] for j in scene.get(paint_scene.LATER, [])}
    percent = {}
    for item in _paintable(data.get("items", [])):
        node = nodes.get(item["id"])
        if node is None or item["id"] in waiting or not pic.of(item["id"]).any():
            continue
        mid = f'{item["id"]}__paint'
        if mid in mats:
            props = dict(out["materials"][mats[mid]]["props"])
            alpha = _alpha_of(props)
        else:
            mid, props, alpha = f'{item["id"]}__cover', _own_props(by_id, node), None
        size = alpha.shape[0] if alpha is not None else min(UNPAINTED_SIZE, int(item.get("paintSize", 2048)))
        alpha = np.zeros((size, size), np.uint8) if alpha is None else alpha
        percent[item["id"]] = measure(pic, {item["id"]: alpha})[item["id"]]["percent"]
        tinted = {"id": mid, "props": {**props, "baseColorTexture": _tinted(props, size, pic, item["id"], alpha, pic_key)}}
        if mid in mats:
            out["materials"][mats[mid]] = {**out["materials"][mats[mid]], **tinted}
        else:
            out["materials"].append(tinted)
            node["props"]["material"] = mid
    return percent, out
