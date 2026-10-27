"""Placing by a pixel of the last look, the way a person clicks. edit_place_highlight: a light by its highlight (SPEC
§7), through `light.place_highlight`. edit_place_on: a mesh standing on the surface there (Place on a surface), with its
mirrored copy when the surface is a clay whose Mirror is on (`mesh.mirror`, rostrum3d/mirror.py). Three picks (the spot
and two neighbours) give the point and the surface's direction; each is one change in the history.
"""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from rostrum3d import aim, highlight as H, shape_size, surface_place, through

from . import draw
from .shot import ITEM_SHOT, TIME, doc_and_shot, frame_of, size_of

tools = Tools()
STEP = 3


def _picks(ctx, scene, info, frame, w, h, x, y) -> list[dict]:
    """The engine's picks at (x, y) and two neighbours, all on one item's surface (else a loud error)."""
    engine = draw.engine_of(ctx)
    hits = [draw.call(ctx.tool, f"point ({x + dx:g}, {y + dy:g})", engine, scene, "pick", camera=info["camera"], frame=frame,
                      width=w, height=h, x=min(x + dx, w - 1), y=min(y + dy, h - 1)) for dx, dy in ((0, 0), (STEP, 0), (0, STEP))]
    if not all(r.get("hit") and r.get("item") == hits[0].get("item") for r in hits):
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"({x:g}, {y:g})", "is not inside one item's surface (background or an edge)",
                           hint="look_at tells what is at a pixel; pick a point a few pixels inside the surface.")
    return hits


@tools.tool("edit_place_highlight", {"required": ["light", "x", "y"], "properties": {
    **ITEM_SHOT, **TIME,
    "light": {"type": "string", "description": "The light's id (rect, disk, strip, sphere, spot or distant)."},
    "x": {"type": "number", "minimum": 0, "description": "Pixels from the left of the picture look_frame gave."},
    "y": {"type": "number", "minimum": 0, "description": "Pixels from the top."},
    "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 960, "description": "That picture's width. Default 960."},
    "fresh": {"type": "boolean", "default": False, "description": "true: also put it 4 × the item's size away with the starting brightness "
                                                                   "(a light just added); false: keep its distance and brightness."}}})
def place_highlight(ctx, args):
    """Move and aim a light so its highlight lands on what is at pixel (x, y) of the shot camera's picture (a sun: its lit side faces it).
    One change in the history. Then look_frame to see it; the reply there says how much is clipped."""
    doc, info = doc_and_shot(ctx, args)
    frame = frame_of(ctx, info, args)
    w, h = size_of(info, args, 960)
    scene, x, y = draw.scene_of(doc, info["id"]), args["x"], args["y"]
    hits = _picks(ctx, scene, info, frame, w, h, x, y)
    cam_world = through.find_item(scene, info["camera"], frame)[0]
    eye, points = aim.point(cam_world, [0.0, 0.0, 0.0]), [r["point"] for r in hits]
    try:
        normal = H.surface_normal(eye, hits)
        item_world, item_values, _ = through.find_item(scene, hits[0]["item"], frame)
    except ValueError as e:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"({x:g}, {y:g})", str(e)) from None
    op = {"point": points[0], "normal": normal, "eye": eye}
    if args.get("fresh"):
        op.update(distance=H.distance_for(H.item_size(item_world, item_values), eye, points[0]), brightness=True)
    change = ctx.apply(doc, [{"op": "light.place_highlight", "target": [args["light"]], "args": op}], "Place highlight")
    lit = doc.item(args["light"])
    where = [round(lit.get(k, 0.0), 3) for k in ("x", "y", "z")]
    return Reply(f'{args["light"]} now stands at {where}, aimed at {[round(c, 3) for c in points[0]]} on {hits[0]["item"]}'
                 + (f', intensity {lit.get("intensity")}' if args.get("fresh") else "") + ".",
                 {"light": args["light"], "item": hits[0]["item"], "point": points[0], "normal": normal, "position": where,
                  "seq": change.seq if change else doc.seq})


@tools.tool("edit_place_on", {"required": ["mesh", "x", "y"], "properties": {
    **ITEM_SHOT, **TIME,
    "mesh": {"type": "string", "description": "The mesh's id (made first, e.g. by run_script, at its size)."},
    "x": {"type": "number", "minimum": 0, "description": "Pixels from the left of the picture look_frame gave."},
    "y": {"type": "number", "minimum": 0, "description": "Pixels from the top."},
    "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 960, "description": "That picture's width. Default 960."},
    "mirror": {"type": "boolean", "default": True, "description": "On a clay whose Mirror is on (and off its middle): also make the "
                                                                  "mesh's mirrored copy, which follows it. false: no copy."}}})
def place_on(ctx, args):
    """Stand a mesh on the surface at pixel (x, y) of the shot camera's picture, its base on the surface along the surface's
    direction there, the way a person places a shape by clicking (an eye on a face). On a clay whose Mirror is on, a point off
    its middle also gives the mesh a mirrored copy on the other side ("<mesh>_mirrored", named "<name> (mirrored)") that
    follows it: edit the original (edits sent to the copy go to it). One change in the history. Then look_frame to see it."""
    doc, info = doc_and_shot(ctx, args)
    frame = frame_of(ctx, info, args)
    w, h = size_of(info, args, 960)
    mesh = doc.item(args["mesh"])
    if mesh["type"] != "mesh" or mesh.get("mirror"):
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, args["mesh"], "is not a mesh" if mesh["type"] != "mesh" else
                           f'is the mirrored copy of {mesh["mirror"]}; place {mesh["mirror"]} (its copy follows)')
    scene = draw.scene_of(doc, info["id"])
    hits = _picks(ctx, scene, info, frame, w, h, args["x"], args["y"])
    on = hits[0]["item"]
    if on == args["mesh"] or doc.item(on).get("mirror") == args["mesh"]:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'({args["x"]:g}, {args["y"]:g})', f"is on {args['mesh']} itself",
                           hint="Pick a pixel on the surface it should stand on.")
    eye = aim.point(through.find_item(scene, info["camera"], frame)[0], [0.0, 0.0, 0.0])
    try:
        normal = H.surface_normal(eye, hits)
    except ValueError as e:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'({args["x"]:g}, {args["y"]:g})', str(e)) from None
    point = hits[0]["point"]
    parent = doc.parent_of(args["mesh"])[0]
    parent_world = through.find_item(scene, parent, frame)[0] if parent and parent != doc.data["id"] else aim.IDENTITY
    calls = [{"op": "mesh.set", "target": [args["mesh"]],
              "args": surface_place.into_parent(surface_place.stand(mesh, point, normal), parent_world)}]
    on_world = through.find_item(scene, on, frame)[0]
    has_copy = any(i.get("mirror") == args["mesh"] for i in doc.items())
    copy = (args.get("mirror", True) and not has_copy
            and surface_place.mirrors(doc.item(on), on_world, point, shape_size.extent(mesh)))
    if copy:
        calls.append({"op": "mesh.mirror", "target": [args["mesh"]], "args": {"on": on}})
    change = ctx.apply(doc, calls, "Place on a surface")
    made = next((i["id"] for i in doc.items() if i.get("mirror") == args["mesh"]), "") if copy else ""
    return Reply(f'{args["mesh"]} now stands on {on} at {[round(c, 3) for c in point]}'
                 + (f"; its mirrored copy {made} follows it." if made else "."),
                 {"mesh": args["mesh"], "on": on, "point": point, "normal": normal, "mirrored": made,
                  "seq": change.seq if change else doc.seq})
