"""Stamp a picture (an "alpha"): `paint.stamp` lays one whole picture, once, as relief on a mesh or a clay: one stroke of
a single dab on the item's Relief paint layer (made when it has none), the picture as the dab's tip picture covering
the whole dab, at the stamp's size and turn. White raises and black sinks (`depth`'s sign), by |depth|. One change,
one undo step. It is a plain kit stroke, so it is laid, seen and checked like any other (a clay's by `anchors`, kept
on its surface through reshapes; a view stamp by `viewPoints`, laid where its camera sees it).

The picture: a picture file (its brightness is the height: white raised most, black flat; a picture with see-through
parts raises where it is opaque), a tip picture kept in the project, or a built-in tip. `tidy` (the document's call
tidy, with the project folder) swaps it for its padded copy (paint_stamp_pictures.py: the round dab never clips its
corners) and gives the dab's `fit`, so the picture itself measures `size`. Turn 0 is upright (stamp_turn.py): from
the view the screen's up, on a clay its +Y on the surface, worked out each time the stamp is laid (`stampTurn`).
"""
from __future__ import annotations

import rostrum_paint.ops as kit_ops
from rostrum_core import Param
from rostrum_core.errors import RostrumError, codes
from rostrum_paint import library, pictures

from . import paint_stamp_pictures, unfold
from .kind import REGISTRY as R
from .ops_paint import XYZ, _shot_view
from .paint_fields import CHANNELS, LAYER, STROKE

CHANNEL = "height"                                   # Relief
DEPTH = Param.number("depth", label="Depth", min=-1, max=1, step=0.01, default=0.5, display="percent", group="Stamp",
                     help="How far the picture raises the surface (above 0) or sinks it (below 0): 100 % = as far as "
                          "Relief goes")
TURN = Param.number("turn", label="Turn", min=-360, max=360, step=1, default=0.0, unit="°", group="Stamp",
                    help="The picture's turn, clockwise as seen: 0 = upright (from the view: the screen's up; on a clay: "
                         "its +Y on the surface; at a `point`: the paint picture's up)")
CAMERA = ("eye", "target", "fov", "width", "height")
# the dab: a hard round tip, the picture over all of it, no drift or pressure, turned by `turn`
DAB = {"brush": "round", "hardness": 1.0, "follow": False, "color_jitter": 0.0, "size_pressure": 0.0,
       "opacity_pressure": 0.0, "even": False}


def dab_values(picture: str, size: float, depth: float, turn: float) -> dict:
    """The kit stroke settings of one whole-picture stamp (its path and size added by the caller)."""
    return {**DAB, "texture": picture, "angle": float(turn), "size": float(size),
            "color": "#ffffff" if depth >= 0 else "#000000", "opacity": round(abs(float(depth)), 4)}


def tidy(calls: list[dict], folder=None) -> list[dict]:
    """Each paint.stamp's picture made ready (the document's call tidy, with the project folder): its padded copy
    in the project, named by the call, and the dab's `fit` (paint_stamp_pictures.prepare)."""
    out = []
    for c in calls:
        args = c.get("args") or {}
        if c.get("op") == "paint.stamp" and isinstance(args.get("picture"), str) and args["picture"]:
            tip, fit = paint_stamp_pictures.prepare(folder, args["picture"])
            c = {**c, "args": {**args, "picture": tip, "fit": fit}}
        out.append(c)
    return out


def _layer(ctx, item: dict, want: str) -> str:
    """The Relief layer the stamp goes on: `want`, else the item's top Relief layer, else a new one (made here)."""
    if want:
        if not any(p["id"] == want for p in item.get("paints", [])):
            ctx.fail(codes.NOT_FOUND, f'layer "{want}"', f'is not a paint layer of {item["id"]}',
                     [p["id"] for p in item.get("paints", [])])
        return want
    mine = [p["id"] for p in item.get("paints", []) if p.get("channel", "colour") == CHANNEL]
    if mine:
        return mine[-1]
    if item["type"] == "mesh" and not item.get("uvs"):
        unfold.mesh_unfold(ctx, [item["id"]], {})            # as paint.add does: a mesh is laid flat first
    n = len(mine) + 1
    layer = kit_ops.build("paint", ctx.new_id("paint"), {"name": f"{CHANNELS[CHANNEL][0]} {n}", "channel": CHANNEL},
                          ctx.where, LAYER)
    ctx.insert(item["id"], "paints", layer)
    return layer["id"]


def _path(ctx, item: dict, args: dict) -> dict:
    """The stroke's path fields from `at` (a clay's surface), `point` (canvas px) or `viewPoint` (+ its camera)."""
    given = [k for k in ("at", "point", "viewPoint") if args.get(k) is not None]
    if len(given) != 1:
        ctx.fail(codes.BAD_ARGUMENT, "at / point / viewPoint", f"needs exactly one of them (got {len(given) or 'none'})",
                 hint="`at` [x, y, z, nx, ny, nz] on a clay (look_at's local + localNormal), `point` [x, y] in paint "
                      "picture px, or `viewPoint` [x, y] in px of a view with its camera.")
    size, turn = float(args["size"]) * float(args.get("fit", 1.0)), float(args.get("turn", 0.0))
    if given[0] == "at":
        if item["type"] != "clay":
            ctx.fail(codes.BAD_ARGUMENT, '"at"', f'is for a clay; {item["id"]} is a {item["type"]}',
                     hint="Give `point` (paint picture px, from look_at's uv) or `viewPoint`.")
        return {"anchors": [[*args["at"], 1.0]], "reach": round(size / 2, 6), "size": 1.0, "stampTurn": turn}
    if given[0] == "point":
        x, y = args["point"]
        return {"points": [[x, y, 1.0]], "size": size}
    free = [k for k in CAMERA if k in args]
    if bool(args.get("shot")) == bool(free) or (free and len(free) < len(CAMERA)):
        ctx.fail(codes.BAD_ARGUMENT, "shot / eye", "a viewPoint needs a shot or a whole free camera (eye, target, "
                 "fov, width, height)")
    view = _shot_view(ctx, args["shot"], args.get("frame")) if args.get("shot") else \
        {**{k: args[k] for k in CAMERA}, "frame": int(args.get("frame", 0))}
    from .paint_view import view_fields
    return {**view_fields({**view, "points": [[*args["viewPoint"], 1.0]]}), "size": size, "stampTurn": turn}


@R.operation("paint.stamp", "Stamp a picture as relief (an \"alpha\"): the whole picture once, at `size` and `turn`, "
             "on the Relief paint layer of each target (`layer`, else its top Relief layer, made when it has none): "
             "raised where the picture is bright (or opaque, for a picture with see-through parts), sunk with a "
             "negative `depth`; the whole picture, corners included, measures `size`; `turn` 0 = upright. Where: `at` "
             "on a clay's surface, `point` on the paint picture, or `viewPoint` clicked in a view (with `shot` or a free camera: lands on what that camera sees there). One stroke per target, "
             "one undo step. Shows in Final (Relief is bump).",
             target=("mesh", "clay"), label="Stamp a picture", importance="secondary",
             params=[Param.text("picture", label="Picture", required=True,
                                help="A picture file (kept in the project: brightness = height), or a tip picture by "
                                     "name (built-in: sponge, speckle …; the project's own by id)"),
                     Param.number("size", label="Size", min=0.00001, max=100000, required=True,
                                  help="The picture's width (its longest side): metres with `at`, paint picture px "
                                       "with `point`, screen px with `viewPoint`"),
                     DEPTH, TURN,
                     Param.list("at", "number", label="On the clay", min_items=6, max_items=6,
                                help="A clay's spot: [x, y, z, nx, ny, nz] in its own space (look_at's local and "
                                     "localNormal; on a posed clay its rest spot)"),
                     Param.list("point", "number", label="On the picture", min_items=2, max_items=2, unit="px",
                                help="[x, y] in the paint picture's px (x = u × paintSize, y = (1 − v) × paintSize)"),
                     Param.list("viewPoint", "number", label="In the view", min_items=2, max_items=2, unit="px",
                                help="[x, y] in px of the view's picture (with shot, or eye … height)"),
                     Param.id("shot", kind="shot", label="Through shot", help="viewPoint: this shot's camera"),
                     Param.number("frame", label="Frame", min=0, max=10_000_000, integer=True,
                                  help="viewPoint: the frame the camera is taken at (default the shot's start)"),
                     Param.list("eye", "number", label="Camera at", **XYZ, help="viewPoint, a free camera: where it stands"),
                     Param.list("target", "number", label="Looking at", **XYZ, help="… the point in the picture's middle"),
                     Param.number("fov", label="Field of view", min=0.1, max=179, unit="°", help="… its vertical angle"),
                     Param.number("width", label="Width", min=1, max=16384, integer=True, unit="px", help="… picture width"),
                     Param.number("height", label="Height", min=1, max=16384, integer=True, unit="px", help="… picture height"),
                     Param.id("layer", kind="paint", label="Layer", help="The paint layer to stamp on (one target)"),
                     Param.number("fit", label="Dab per picture", min=1, max=4, importance="deep",
                                  help="Set by Rostrum: how much wider the round dab is than the picture (its padded "
                                       "copy), so the whole picture lies inside it")])
def paint_stamp(ctx, targets, args):
    pic = args["picture"]
    try:
        pictures.tip(pic)                                    # loud when the picture isn't a tip of this project
    except (RostrumError, ValueError) as e:
        ctx.fail(codes.NOT_FOUND, '"picture"', f'"{pic}" is not a tip picture here ({e})',
                 [c["value"] for c in library.choices("tip") if c["value"] != "none"],
                 hint="Give a picture file, or a tip picture's name.")
    if pic == "none":
        ctx.fail(codes.BAD_ARGUMENT, '"picture"', '"none" is no picture')
    if args.get("layer") and len(targets) != 1:
        ctx.fail(codes.BAD_ARGUMENT, '"layer"', "names one item's layer: give one target")
    made = []
    for t in targets:
        item = ctx.item(t)
        path = _path(ctx, item, args)
        layer = _layer(ctx, item, args.get("layer", ""))
        values = {**dab_values(pic, path.pop("size"), args.get("depth", DEPTH.default), args.get("turn", 0.0)), **path}
        stroke = kit_ops.build("stroke", ctx.new_id("stroke"), values, ctx.where, STROKE)
        ctx.insert(layer, "strokes", stroke)
        made.append({"item": t, "layer": layer, "stroke": stroke["id"]})
    return {"stamps": made}
