"""Painted meshes and clays → the scene (SPEC §5 "Materials meet paint"), for compile.describe. For each mesh or clay
holding paint layers and each channel they paint (paint_fields.CHANNELS), the channel's layers (the shared kit's
canvas, its own cache) are laid over the material's own value where painted: its colour or number, or its own picture
for that channel. The result is one content-keyed PNG per channel (the shared cache, kind "paint"): made once, then
only read. The item gets a material of its own, `<item>__paint`, a copy of its material with those pictures set
(baseColorTexture, roughnessTexture, bumpTexture, metallicTexture, emissionTexture); both renderers read them on the
mesh's `uvs` or the clay's unfolded surface. Face materials (an editable mesh's, an outline's front / side) keep
their own, unpainted.

A painted clay's node gets `paint` {file, size}: where the core keeps its unfolded surface for this shape
(clay_paint.surface_file). Its strokes are laid on that surface (clay_paint.laid), so the file must be there first:
when it isn't yet (a new shape), the clay's pictures wait in `scene["paintLater"]` (a JSON recipe) and `send` loads
the scene without them (the core writes the file while it loads), then makes them and loads again.
"""
from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
from rostrum_core.cache import CACHE, cache_key
from rostrum_paint import canvas

from . import clay_paint
from .material_fields import DOC_ONLY, MATERIAL
from .paint_fields import CHANNELS

VERSION = f"rostrum3d-paint-surface@1+{canvas.ENGINE_VERSION}"
LATER = "paintLater"


def _canvases(items: list):
    for it in items:
        if it.get("type") in ("mesh", "clay") and it.get("paints"):
            yield it
        yield from _canvases(it.get("children", []))


def _nodes(nodes: list, out: dict) -> dict:
    for n in nodes:
        out[n["id"]] = n
        _nodes(n.get("children", []), out)
    return out


def _rgb(hex_: str) -> list[float]:
    return [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def _under(channel: str, mat: dict) -> tuple:
    """What the paint sits over: ("file", path) for the material's own picture of the channel, else ("value", [r, g, b]
    sRGB 0..1, or [v] for a raw number)."""
    _, picture, own, raw = CHANNELS[channel]
    if channel == "glow" and mat.get("emissionRender"):
        return "value", [0.0, 0.0, 0.0]             # a playing 2D render can't be painted over yet: paint replaces it
    if mat.get(picture):
        return "file", mat[picture]
    if channel == "glow":
        return "value", _rgb(mat["emissionColor"]) if mat["emissionStrength"] else [0.0, 0.0, 0.0]
    if own is None:
        return "value", [0.0]                       # height: flat
    return "value", [float(mat[own])] if raw else _rgb(mat[own])


def _picture(held: dict, channel: str, layers: list, size: int, under: tuple, surface: str = "") -> Path:
    raw = CHANNELS[channel][3]
    held = {"id": held["id"], "paints": layers, "paintmasks": held.get("paintmasks", [])}
    settings = {"size": size, "channel": channel, "under": list(under), **({"surface": surface} if surface else {})}
    key = cache_key("paint.surface", VERSION, [canvas.content_key(held, size, size)], settings)
    if CACHE.get("paint", key):
        return CACHE.path("paint", key) / "surface.png"

    def make(tmp: Path):
        from PIL import Image
        px = canvas.rgba8(held, size, size).astype(np.float32) / 255
        a, rgb = px[..., 3:], px[..., :3]
        paint = rgb.mean(axis=2, keepdims=True) if raw else rgb      # raw channels: the brush colour's grey
        if under[0] == "file":
            with Image.open(under[1]) as im:
                base = np.asarray(im.convert("L" if raw else "RGB").resize((size, size)), np.float32) / 255
            base = base[..., None] if raw else base
        else:
            base = np.broadcast_to(np.asarray(under[1], np.float32), paint.shape)
        out = np.clip(paint * a + base * (1 - a), 0, 1) * 255 + 0.5
        img = out[..., 0] if raw else out
        Image.fromarray(img.astype(np.uint8), "L" if raw else "RGB").save(tmp / "surface.png", compress_level=1)
    return CACHE.put("paint", key, make, {"item": held["id"], "channel": channel, "size": size}) / "surface.png"


def paint(scene: dict, data: dict, out_value) -> None:
    """Give every painted mesh and clay of `scene` (compile.describe's, from document `data`) its painted material,
    in place (a clay whose surface isn't made yet: its recipe in scene["paintLater"]). `out_value(param, value)`: the
    compiler's one way a value is sent."""
    nodes = _nodes(scene["items"], {})
    sent = {m["id"]: m for m in scene["materials"]}
    own = {m["id"]: m for m in data.get("materials", [])}
    for item in _canvases(data.get("items", [])):
        node = nodes.get(item["id"])
        if node is None:
            continue
        mid = node["props"].get("material", "")
        base = sent.get(mid) or {"props": {p.name: out_value(p, p.default) for p in MATERIAL if p.name not in DOC_ONLY}}
        job = {"item": {k: item[k] for k in ("id", "type", "paints", "paintmasks", "paintSize") if k in item},
               "mat": {p.name: own.get(mid, {}).get(p.name, p.default) for p in MATERIAL},
               "base": {k: base[k] for k in ("props", "anim") if base.get(k)}}
        if item["type"] == "clay":
            if not node.get("steps"):
                continue                                 # an empty clay: no surface to paint on
            size = item.get("paintSize", 2048)
            f = clay_paint.surface_file(node["steps"][-1]["key"], node["props"]["detail"], size)
            node["paint"] = {"file": str(f), "size": size}
            if not f.is_file():
                scene.setdefault(LATER, []).append(job)
                continue
        _apply(scene, node, job)


def _apply(scene: dict, node: dict, job: dict) -> None:
    """One painted item's pictures and its `<id>__paint` material (job: paint's recipe)."""
    item, mat, base = job["item"], job["mat"], job["base"]
    surface = clay_paint.read(node["paint"]["file"]) if "paint" in node else None
    held = clay_paint.laid(item, surface) if surface is not None else item
    by_channel: dict[str, list] = {}
    for layer in held["paints"]:
        by_channel.setdefault(layer.get("channel", "colour"), []).append(layer)
    props = dict(base["props"])
    size = item.get("paintSize", 2048)
    for channel, layers in by_channel.items():
        props[CHANNELS[channel][1]] = str(_picture(held, channel, layers, size, _under(channel, mat),
                                                   surface.key if surface is not None else ""))
    if "glow" in by_channel and not props.get("emissionStrength"):
        props["emissionStrength"] = 1.0            # painted glow shows at strength 1 on a material that had none
    new = {"id": f"{item['id']}__paint", "props": props}
    if base.get("anim") and "glow" not in by_channel:
        new["anim"] = base["anim"]
    scene["materials"].append(new)
    node["props"]["material"] = new["id"]


def finish(scene: dict, later: list) -> dict:
    """A copy of `scene` (loaded once without its waiting pictures, so the core has written the clays' surfaces) with
    those pictures made and set. Fails loudly when a surface is still missing."""
    done = copy.deepcopy(scene)
    nodes = _nodes(done["items"], {})
    for job in later:
        node = nodes[job["item"]["id"]]
        f = Path(node["paint"]["file"])
        if not f.is_file():
            raise RuntimeError(f'clay {job["item"]["id"]}: the 3D engine loaded it but wrote no unfolded surface at {f}, '
                               "so its paint can't be laid (see the engine's log)")
        _apply(done, node, job)
    return done


def send(scene: dict, load):
    """Load `scene` through `load(scene)` (an engine's). A scene with clays waiting for their surface (paintLater) is
    loaded without them first, then again with their pictures (`finish`): what the second load returns."""
    later = scene.get(LATER)
    if not later:
        return load(scene)
    first = {k: v for k, v in scene.items() if k != LATER}
    load(first)
    return load(finish(first, later))


def surface_of(scene: dict, item_id: str) -> Path | None:
    """The clay `item_id`'s unfolded surface file in `scene` when it is made, else None."""
    node = _nodes(scene.get("items", []), {}).get(item_id) or {}
    f = Path(node["paint"]["file"]) if node.get("paint") else None
    return f if f is not None and f.is_file() else None
