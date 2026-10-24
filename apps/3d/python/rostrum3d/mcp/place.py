"""edit_place_highlight: an agent places a light by its highlight, in pixels of the last look (SPEC §7), the way a person
Alt+clicks. Three picks (the spot and two neighbours) give the point and the surface's direction; then the one operation
the screen uses, `light.place_highlight`, as one change in the history.
"""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from rostrum3d import aim, highlight as H, through

from . import draw
from .shot import ITEM_SHOT, TIME, doc_and_shot, frame_of, size_of

tools = Tools()
STEP = 3


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
    scene, engine = draw.scene_of(doc, info["id"]), draw.engine_of(ctx)
    x, y = args["x"], args["y"]
    hits = [draw.call(ctx.tool, f"point ({x + dx:g}, {y + dy:g})", engine, scene, "pick", camera=info["camera"], frame=frame,
                      width=w, height=h, x=min(x + dx, w - 1), y=min(y + dy, h - 1)) for dx, dy in ((0, 0), (STEP, 0), (0, STEP))]
    if not all(r.get("hit") and r.get("item") == hits[0].get("item") for r in hits):
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"({x:g}, {y:g})", "is not inside one item's surface (background or an edge)",
                           hint="look_at tells what is at a pixel; pick a point a few pixels inside the surface.")
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
