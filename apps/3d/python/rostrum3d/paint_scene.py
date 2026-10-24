"""Painted meshes → the scene (SPEC §5 "Materials meet paint"), for compile.describe. For each mesh holding paint
layers and each channel they paint (paint_fields.CHANNELS), the channel's layers (the shared kit's canvas, its own
cache) are laid over the material's own value where painted: its colour or number, or its own picture for that
channel. The result is one content-keyed PNG per channel (the shared cache, kind "paint"): made once, then only read.
The mesh gets a material of its own, `<item>__paint`, a copy of its material with those pictures set
(baseColorTexture, roughnessTexture, bumpTexture, metallicTexture, emissionTexture); both renderers read them on the
mesh's `uvs`. Face materials (an editable mesh's, an outline's front / side) keep their own, unpainted.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from rostrum_core.cache import CACHE, cache_key
from rostrum_paint import canvas

from .material_fields import DOC_ONLY, MATERIAL
from .paint_fields import CHANNELS

VERSION = f"rostrum3d-paint-surface@1+{canvas.ENGINE_VERSION}"


def _meshes(items: list):
    for it in items:
        if it.get("type") == "mesh" and it.get("paints"):
            yield it
        yield from _meshes(it.get("children", []))


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


def _picture(item: dict, channel: str, layers: list, size: int, under: tuple) -> Path:
    raw = CHANNELS[channel][3]
    held = {"id": item["id"], "paints": layers, "paintmasks": item.get("paintmasks", [])}
    key = cache_key("paint.surface", VERSION, [canvas.content_key(held, size, size)],
                    {"size": size, "channel": channel, "under": list(under)})
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
    return CACHE.put("paint", key, make, {"item": item["id"], "channel": channel, "size": size}) / "surface.png"


def paint(scene: dict, data: dict, out_value) -> None:
    """Give every painted mesh of `scene` (compile.describe's, from document `data`) its painted material, in place.
    `out_value(param, value)`: the compiler's one way a value is sent."""
    nodes = _nodes(scene["items"], {})
    sent = {m["id"]: m for m in scene["materials"]}
    own = {m["id"]: m for m in data.get("materials", [])}
    for item in _meshes(data.get("items", [])):
        node = nodes.get(item["id"])
        by_channel: dict[str, list] = {}
        for layer in item["paints"]:
            by_channel.setdefault(layer.get("channel", "colour"), []).append(layer)
        if node is None or not by_channel:
            continue
        mid = node["props"].get("material", "")
        mat = {p.name: own.get(mid, {}).get(p.name, p.default) for p in MATERIAL}
        base = sent.get(mid) or {"props": {p.name: out_value(p, p.default) for p in MATERIAL if p.name not in DOC_ONLY}}
        props = dict(base["props"])
        size = item.get("paintSize", 2048)
        for channel, layers in by_channel.items():
            props[CHANNELS[channel][1]] = str(_picture(item, channel, layers, size, _under(channel, mat)))
        if "glow" in by_channel and not props.get("emissionStrength"):
            props["emissionStrength"] = 1.0            # painted glow shows at strength 1 on a material that had none
        new = {"id": f"{item['id']}__paint", "props": props}
        if base.get("anim") and "glow" not in by_channel:
            new["anim"] = base["anim"]
        scene["materials"].append(new)
        node["props"]["material"] = new["id"]
