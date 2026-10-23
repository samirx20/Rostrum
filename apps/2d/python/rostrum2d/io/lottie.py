"""Scene description → Lottie JSON (bodymovin 5.x) and a report of everything Lottie couldn't carry.

`to_lottie(scene)` → (lottie dict, report). `write_lottie(scene, path)` writes the file and returns the report.
The report is what will differ from the preview; what is carried exactly as a keyframe every frame (springs, colour
fades, the camera) is not a difference and goes to the `baked` list a caller may pass.

- shape, path: Lottie shape layers (lottie_shapes.py). Images: image layers with the file embedded (lottie_image.py).
- group: a precomp layer (so the group's opacity, blend, masks and keys apply to it as a whole); its children are the
  precomp's layers, in the group's own px. `clip` becomes a rect mask over the box; otherwise the precomp is made
  huge so nothing is cut. Time inside a precomp is the composition's time.
- The composition's background becomes the bottom solid layer (Lottie has no background colour).
- camera: baked into null parent layers, a keyframe every frame (lottie_camera.py), so the picture matches.
- text: glyph outlines as one shape layer per text (lottie_text.py). Not exported, always reported: drawing, video, tilt, effects, motion blur, conic gradients, soft mask edges.
"""
from __future__ import annotations

import json
from pathlib import Path

from .lottie_camera import bake as bake_camera
from .lottie_image import image_layer
from .lottie_layer import clip_mask, common
from .lottie_outline import Outlines
from .lottie_props import Ctx, rgb
from .lottie_shapes import shapes_of
from .lottie_text import text_layer

VERSION = "5.12.2"
BIG = 32768          # a precomp without `clip` is this big, so lottie-web never cuts a child at the group's box
NOT_EXPORTED = {"drawing": "frame-by-frame drawings are not exported (Lottie has no brush layers)",
                "video": "video layers are not exported (Lottie holds no video)"}


def _layers(children: list[dict], ctx: Ctx, assets: list[dict], start_ind: int = 1) -> list[dict]:
    """Our layers (bottom first) → Lottie layers (top first)."""
    out, ctx.siblings = [], children
    for node in children:
        ctx.layer = node["id"]
        kind = node["type"]
        if node["props"]["end"] <= node["props"]["start"]:
            ctx.say("starts after it ends; never drawn, so not exported")
            continue
        if kind in NOT_EXPORTED:
            ctx.say(NOT_EXPORTED[kind])
            continue
        if kind == "camera":                   # a composition's own: bake_camera carries it, after the layers
            continue
        ind = start_ind + len(out)
        if kind in ("shape", "path"):
            layer = common(node, ctx, 4, ind)
            layer["shapes"] = shapes_of(node, ctx)
        elif kind == "text":
            layer = text_layer(node, ctx, ind)
            if not layer:                      # font not found: text_layer said so
                continue
        elif kind == "image":
            layer = image_layer(node, ctx, assets, ind)
        elif kind == "group":
            layer = _group(node, ctx, assets, ind)
        else:                                  # a kind Lottie can't carry is left out and listed, never a failed export
            ctx.say(f'a "{kind}" layer is not exported (Lottie has no such layer)')
            continue
        if kind != "image":
            _gradient_note(node, ctx, kind)
        out.append(layer)
    return out[::-1]


def _gradient_note(node: dict, ctx: Ctx, kind: str) -> None:
    if kind == "group" and any(e["type"] == "gradient" for e in node.get("effects", [])):
        ctx.say("gradient on a group's background is not exported")


def _group(node: dict, ctx: Ctx, assets: list[dict], ind: int) -> dict:
    pr, name = node["props"], f'group_{node["id"]}'
    inner = Ctx(ctx.fps, ctx.duration, ctx.report, outlines=ctx.outlines)
    kids = _layers(node.get("layers", []), inner, assets)
    ctx.layer = node["id"]
    for k, i in zip(kids, range(len(kids), 0, -1)):      # indices count from the bottom layer
        k["ind"] = i
    assets.append({"id": name, "layers": kids})
    layer = common(node, ctx, 0, ind, [clip_mask(node)] if pr["clip"] else [])
    layer.update({"refId": name, "w": round(pr["w"]) if pr["clip"] else BIG, "h": round(pr["h"]) if pr["clip"] else BIG})
    return layer


def _background(comp: dict, ind: int) -> dict:
    pr = comp["props"]
    ks = {"a": {"a": 0, "k": [0, 0, 0]}, "p": {"a": 0, "k": [0, 0, 0]}, "s": {"a": 0, "k": [100, 100, 100]},
          "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100}}
    return {"ddd": 0, "ind": ind, "ty": 1, "nm": "background", "sr": 1, "ks": ks, "ao": 0, "sw": pr["width"],
            "sh": pr["height"], "sc": pr["background"], "ip": 0, "op": round(pr["duration"] * pr["fps"]), "st": 0, "bm": 0}


def _round(v):
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, list):
        return [_round(x) for x in v]
    if isinstance(v, dict):
        return {k: _round(x) for k, x in v.items()}
    return v


def to_lottie(scene: dict, background: bool = True, baked: list | None = None) -> tuple[dict, list[str]]:
    """The scene description (rostrum2d.scene.describe) → (Lottie JSON as a dict, report sentences); `baked` gets the
    lines for what is carried as a keyframe every frame."""
    if scene.get("format") != "rostrum-2d-scene":
        raise ValueError(f'not a scene description (format "{scene.get("format")}")')
    comp = scene["comp"]
    pr = comp["props"]
    outlines = Outlines(scene)
    ctx, assets = Ctx(float(pr["fps"]), float(pr["duration"]), outlines=outlines), []
    try:
        layers = _layers(comp.get("layers", []), ctx, assets)
    finally:
        outlines.close()
    for i, layer in enumerate(layers):
        layer["ind"] = len(layers) - i
    layers += bake_camera(comp, layers, ctx, len(layers) + 1)
    if pr.get("shutter", 0) > 0:
        ctx.report.append(f'composition "{comp["id"]}": motion blur ({pr["shutter"]:g}° shutter) is not in Lottie; moving layers are sharp')
    if background:
        layers.append(_background(comp, len(layers) + 1))
    doc = {"v": VERSION, "fr": pr["fps"], "ip": 0, "op": round(pr["duration"] * pr["fps"]), "w": pr["width"],
           "h": pr["height"], "nm": comp["id"], "ddd": 0, "assets": assets, "layers": layers}
    if baked is not None:
        baked.extend(ctx.baked)
    return _round(doc), ctx.report


def write_lottie(scene: dict, path: str | Path, background: bool = True, baked: list | None = None) -> list[str]:
    """Write the Lottie file (UTF-8 JSON); returns the report."""
    doc, report = to_lottie(scene, background, baked)
    Path(path).write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    return report
