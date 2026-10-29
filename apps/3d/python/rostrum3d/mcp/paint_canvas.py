"""A painted mesh's or clay's canvas as the renderer lays it, for the agent paint tools (paint_look.py, look_at): a
clay's anchored strokes laid on its unfolded surface (clay_paint.laid), strokes from the view laid through their
camera's texel picture (paint_view), so what an agent sees is what the picture gets (preview ≡ export)."""
from __future__ import annotations

import numpy as np
from rostrum_core.errors import RostrumError, codes

from rostrum3d import clay_paint, ops_paint, paint_scene, paint_view, texels
from rostrum3d.paint_fields import CHANNELS

from . import draw

PAINTABLE = ("mesh", "clay")


def size_of(item: dict) -> int:
    return int(item.get("paintSize", 2048))


def paintable(ctx, doc, item_id: str) -> dict:
    """The mesh or clay `item_id`; loud for anything else."""
    if not doc.has(item_id):
        raise RostrumError.not_found(ctx.tool, "item", item_id, [i["id"] for i in doc.items() if i.get("type") in PAINTABLE][:12],
                                     "this document's meshes and clays")
    item = doc.item(item_id)
    if item.get("type") not in PAINTABLE:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'"{item_id}"', f'is a {item.get("type")}; only a mesh or a clay holds paint')
    return item


def has_view(item: dict) -> bool:
    """Holds strokes From the view or projected pictures: laid through the engine's texel pictures."""
    return any(paint_view.projected_of(p) or any(paint_view.view_of(s) for s in p.get("strokes", [])) for p in item.get("paints", []))


def loaded(ctx, scene: dict) -> dict:
    """`scene` in the engine (so a clay's unfolded surface file exists), the same failure rule as draw.call."""
    draw.call(ctx.tool, "the scene", draw.engine_of(ctx), scene, "ensure_scene", scene)
    return scene


def _ask(ctx, scene: dict):
    """The engine's texel request (req -> reply), the scene loaded first: texels.cached's `ask`."""
    engine = draw.engine_of(ctx)
    return lambda req: draw.call(ctx.tool, "what a view sees (texels)", engine, scene, "texels_reply", req)


def texels_for(ctx, scene: dict):
    """pic_of(req) -> texels.Picture for a texel request (paint_view.req_of), from the shared cache the renderer's
    paint uses (texels.cached on paint_scene.geometry_scene), else drawn by the engine holding `scene`."""
    geo, ask = paint_scene.geometry_scene(scene), _ask(ctx, scene)
    return lambda req: texels.cached(geo, req, ask)


def laid(ctx, scene: dict | None, item: dict, folder=None) -> dict:
    """The kit canvas of `item` as the renderer lays it (paint_scene.laid_canvas): clay anchors on its surface, view
    strokes and projected pictures through their camera (kept as `splats`, composed by `picture`). `scene`: the shot's
    compiled scene, needed for a clay or a view (loaded in the engine here)."""
    surface = None
    if item["type"] == "clay" and item.get("paints"):
        surface = paint_scene.surface_of(loaded(ctx, scene), item["id"])
        if surface is None:
            raise RostrumError(codes.RENDER_FAILED, ctx.tool, f'clay "{item["id"]}"', "has no unfolded surface yet, so its paint can't be laid",
                               hint="An empty clay has no surface; add a step first.")
    view = has_view(item)
    try:
        held, splats = paint_scene.laid_canvas({**item, "paints": item.get("paints", [])}, surface,
                                               _ask(ctx, loaded(ctx, scene)) if view else None, folder, scene if view else None)
    except ValueError as e:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'"{item["id"]}"', str(e)) from e
    # what its masks are worked out from (paint_scene._masked): the item as kept, a clay's surface
    return {**held, "splats": splats, "kept": item, "surface": clay_paint.read(surface) if surface else None}


def picture(held: dict, size: int, layer: str | None = None, channel: str | None = None) -> np.ndarray:
    """(S, S, 4) uint8 straight alpha: one layer, one channel's layers, or every layer together; a projected layer's
    picture under its own strokes, a filled one covering it all, a masked one only where its mask is: as paint_scene
    lays them."""
    paints = [p for p in held["paints"] if (layer is None or p["id"] == layer) and (channel is None or p.get("channel", "colour") == channel)]
    if layer:
        paints = [{**p, "visible": True} for p in paints]
    splats = {k: v for k, v in held.get("splats", {}).items() if any(p["id"] == k for p in paints)}
    kept = held.get("kept")
    if kept is not None:                   # a masked layer shows only where its mask is, as the render has it
        kept = {**kept, "paints": [p for p in kept.get("paints", []) if any(q["id"] == p["id"] for q in paints)]}
    try:
        px = paint_scene.canvas_rgba({**held, "paints": paints}, size, splats, kept, held.get("surface"))
    except ValueError as e:                # a mask whose shape isn't known: said, as the render says it
        raise RostrumError(codes.BAD_ARGUMENT, "paint look", f'"{held["id"]}"', str(e)) from e
    return np.asarray(px, np.uint8)


def alpha(held: dict, size: int) -> np.ndarray:
    """(S, S) float 0..1: how much paint of any layer covers each canvas pixel (zeros with no layer)."""
    if not held["paints"]:
        return np.zeros((size, size), np.float32)
    return picture(held, size)[..., 3].astype(np.float32) / 255


def top_painted(held: dict, size: int, uv) -> dict | None:
    """{layer, name, channel, colour, alpha} of the topmost shown layer with paint at `uv`, or None."""
    if not held["paints"] or uv is None or not np.isfinite(uv).all():
        return None
    x = min(size - 1, max(0, int(uv[0] * size)))
    y = min(size - 1, max(0, int((1 - uv[1]) * size)))
    for p in reversed(held["paints"]):
        if not p.get("visible", True):
            continue
        px = picture(held, size, layer=p["id"])[y, x]
        if px[3]:
            ch = p.get("channel", "colour")
            return {"layer": p["id"], "name": p.get("name", p["id"]), "channel": ch, "channelLabel": CHANNELS[ch][0],
                    "colour": "#%02x%02x%02x" % tuple(int(c) for c in px[:3]), "alpha": round(px[3] / 255, 3), "canvasPx": [x, y]}
    return None


def about(ctx, doc, scene: dict, hit: dict, kept: dict) -> dict:
    """look_at's paint extras for a hit: `faceSet` (a mesh's own material on that face, when it has face materials) and
    `painted` (the top painted layer there). `kept`: laid canvases per item over one call's points."""
    if not hit.get("hit") or not doc.has(hit.get("item", "")):
        return {}
    item, out = doc.item(hit["item"]), {}
    faces = item.get("faceMaterials") or []
    if faces and hit.get("face") is not None and 0 <= hit["face"] < len(faces):
        out["faceSet"] = faces[hit["face"]] or item.get("material") or ""
    if item.get("type") in PAINTABLE and item.get("paints") and hit.get("uv"):
        if item["id"] not in kept:
            kept[item["id"]] = laid(ctx, scene, item, doc.folder)
        top = top_painted(kept[item["id"]], size_of(item), np.asarray(hit["uv"], np.float64))
        if top:
            out["painted"] = top
    return out


def shot_view(doc, info: dict, frame: int, width: int, height: int) -> dict:
    """The stroke.add fields of a stroke From the view drawn on a width × height picture through the shot at `frame`
    (viewEye, viewTarget, viewFov, viewSize, viewFrame, viewShot; add viewPoints in that picture's px): the shot camera
    as a free camera, the one way paint.project makes it (ops_paint.shot_pose)."""
    shot = next(s for s in doc.data["shots"] if s["id"] == info["id"])
    pose = ops_paint.shot_pose(doc.data, shot, frame, width, height)
    out = paint_view.view_fields({**pose, "points": [], "shot": info["id"]})
    del out["viewPoints"]
    return out
