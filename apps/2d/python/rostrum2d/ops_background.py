"""Painted backgrounds: operations. `background.add` sets up depth layers (far → near drawing layers, each at a
camera depth and big enough for everything the camera shows of it over the shot); `background.move` moves paint
layers or strokes into another drawing (a depth layer), keeping where they sit in the composition, so a flat painting
becomes a parallax background. Each call is one change = one undo step. The maths is background.py.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.tree import index
from rostrum_paint.ops import build

from . import background as B, drawing as D
from .kind import REGISTRY as R
from .ops_draw import _fresh, starter_frame
from .ops_items import new_item

MAX_CANVAS = 8192       # the drawing layer's canvas limit (fields.py)


@R.operation("background.add", "Set up a painted background in depth layers: one drawing layer per depth, far to near, "
             "under the other layers. Each is placed at its camera depth and sized to cover all the camera shows of it "
             "over the composition (pans, push-ins, roll). Key the camera first, or resize later with background.fit.",
             target="comp", label="Add painted background",
             params=[Param.list("depths", "number", label="Depths (far → near)", min=-0.99, max=1000, default=[3.0, 1.0, 0.25],
                                help="Camera depth of each layer, far first: 0 = on the camera's plane, 1 = moves half as much"),
                     Param.list("names", "text", label="Names", importance="secondary", help="One per depth; Far / Mid / Near when left out"),
                     Param.number("bleed", label="Bleed", min=0, max=2000, unit="px", default=B.BLEED, importance="deep",
                                  help="Extra canvas past the furthest edge the camera shows"),
                     Param.number("index", label="Position", min=0, max=100000, integer=True, importance="deep",
                                  help="Where the farthest layer goes in the stack (0 = bottom, the default)")])
def background_add(ctx, targets, args):
    depths = list(args.get("depths") or [3.0, 1.0, 0.25])
    if depths != sorted(depths, reverse=True):
        ctx.fail(codes.BAD_ARGUMENT, f"depths={depths}", "must go far to near (largest depth first)")
    names = list(args.get("names") or B.depth_names(depths))
    if len(names) != len(depths):
        ctx.fail(codes.BAD_ARGUMENT, f"names={names}", f"needs one name per depth ({len(depths)})")
    for t in targets:
        comp, at = ctx.item(t), args.get("index", 0)
        shots = B.shots(comp)
        for n, (depth, name) in enumerate(zip(depths, names)):
            box = _fits(ctx, B.cover(comp, depth, args.get("bleed", B.BLEED), shots), name)
            item = new_item(ctx, "drawing", {"name": name}, depth=depth, **box)
            ctx.insert(t, "layers", item, at + n)
            frame = starter_frame(ctx)
            frame["paints"][0]["name"] = "Paint"
            ctx.insert(item["id"], "frames", frame)


@R.operation("background.fit", "Resize drawing layers so they cover everything the camera shows of them at their depth "
             "over the composition (after the camera changed). Strokes keep their place in the composition.",
             target="drawing", label="Fit to camera", importance="secondary",
             params=[Param.number("bleed", label="Bleed", min=0, max=2000, unit="px", default=B.BLEED, importance="deep")])
def background_fit(ctx, targets, args):
    for t in targets:
        layer, comp = ctx.item(t), _comp_of(ctx, t)
        box = _fits(ctx, B.cover(comp, layer.get("depth", 0.0), args.get("bleed", B.BLEED)), t)
        new = {**layer, **box, "scale": 1.0, "scaleX": 1.0, "scaleY": 1.0, "anchorX": 0.5, "anchorY": 0.5}
        for frame in layer.get("frames", []):
            for paint in frame.get("paints", []):
                for s in list(paint.get("strokes", [])):
                    _shift(ctx, s, layer, new)
            for m in frame.get("paintmasks", []):
                _shift(ctx, m, layer, new)
        for k, v in box.items():
            ctx.set(t, k, v)
        for k in ("scale", "scaleX", "scaleY", "anchorX", "anchorY"):
            ctx.set(t, k, new[k])


@R.operation("background.move", "Move paint layers or strokes into another drawing layer (a depth layer), keeping where "
             "they sit in the composition: to split a flat painting into far / mid / near for parallax. A paint layer "
             "moves whole; strokes go into a paint layer of the same name there (made if missing), or into `paint`.",
             target=("paint", "stroke"), label="Move to depth layer",
             params=[Param.id("into", kind="drawing", label="Into", required=True, help="The drawing layer to move into"),
                     Param.id("paint", kind="paint", label="Paint layer", importance="secondary",
                              help="For strokes: this paint layer of `into` (default: same name as where they came from)"),
                     Param.number("frame", label="At frame", min=0, max=10**7, integer=True, default=0, importance="deep",
                                  help="Which drawing of `into` takes them: the one shown at this frame")])
def background_move(ctx, targets, args):
    dst = ctx.item(args["into"])
    if dst.get("type") != "drawing":
        ctx.fail(codes.BAD_ARGUMENT, f'into "{args["into"]}"', f"is a {dst.get('type')}, not a drawing layer")
    frame = D.frame_at(dst, args.get("frame", 0))
    if frame is None:
        ctx.fail(codes.NOT_FOUND, f'{args["into"]} at frame {args.get("frame", 0)}', "shows no drawing", hint="Add one with frame.add.")
    copies = {}         # (source drawing, mask id) -> its copy in `into`, made once per call
    for t in targets:
        item, src = ctx.item(t), _drawing_of(ctx, t)
        if src["id"] == dst["id"] and not args.get("paint"):
            ctx.fail(codes.BAD_ARGUMENT, f'"{t}"', f"is already in {dst['id']}")
        for s in list(item["strokes"] if item["type"] == "paint" else [item]):
            _shift(ctx, s, src, dst)
            if s.get("mask") and src["id"] != dst["id"]:
                _carry_mask(ctx, s, src, dst, frame, copies)
        if item["type"] == "paint":
            ctx.move(t, frame["id"], "paints")
        else:
            ctx.move(t, _paint_for(ctx, frame, args.get("paint"), _parent(ctx, t)), "strokes")


def _fits(ctx, box, name):
    if box["w"] > MAX_CANVAS or box["h"] > MAX_CANVAS:
        ctx.fail(codes.BAD_ARGUMENT, f'"{name}"', f"would need a {box['w']}×{box['h']} canvas; a drawing is at most {MAX_CANVAS} px a side",
                 hint="Use a larger depth for it (it moves less), a shorter camera move, or split it into two drawing layers.")
    return box


def _shift(ctx, item, src, dst):
    """Rewrite a stroke's (or mask's) points from src's canvas px to dst's, through comp px; strokes keep their size."""
    pts = []
    for p in item["points"]:
        x, y = B.from_comp(dst, *B.to_comp(src, p[0], p[1]))
        pts.append([round(x, 2), round(y, 2), *p[2:]])
    ctx.set(item["id"], "points", pts)
    if item["type"] == "stroke":
        ctx.set(item["id"], "size", round(item["size"] * B.size_ratio(src, dst), 3))


def _carry_mask(ctx, stroke, src, dst, frame, copies):
    """A stroke clipped by a mask brings a copy of the mask (in dst's canvas px), made once per mask."""
    key = (src["id"], stroke["mask"])
    if key not in copies:
        mask = next(m for f in src["frames"] for m in f.get("paintmasks", []) if m["id"] == stroke["mask"])
        copies[key] = _fresh(ctx, "paintmask")
        pts = [list(B.from_comp(dst, *B.to_comp(src, *p[:2]))) for p in mask["points"]]
        ctx.insert(frame["id"], "paintmasks", {**mask, "id": copies[key], "points": pts})
    ctx.set(stroke["id"], "mask", copies[key])


def _paint_for(ctx, frame, paint_id, src_paint) -> str:
    if paint_id:
        if paint_id not in [p["id"] for p in frame["paints"]]:
            ctx.fail(codes.NOT_FOUND, f'paint "{paint_id}"', f"is not a paint layer of {frame['id']}", [p["id"] for p in frame["paints"]])
        return paint_id
    name = ctx.item(src_paint).get("name", "Paint")
    for p in frame["paints"]:
        if p.get("name") == name:
            return p["id"]
    new = build("paint", _fresh(ctx, "paint"), {"name": name}, ctx.where)
    ctx.insert(frame["id"], "paints", new)
    return new["id"]


def _parent(ctx, id_):
    return index(ctx.doc, ctx.kind.lists)[id_].parent


def _drawing_of(ctx, id_):
    cur = id_
    while ctx.item(cur).get("type") != "drawing":
        cur = _parent(ctx, cur)
    return ctx.item(cur)


def _comp_of(ctx, id_):
    cur = _parent(ctx, id_)
    if ctx.item(cur).get("type") != "comp":
        ctx.fail(codes.BAD_ARGUMENT, f'"{id_}"', "is inside a group or rig: only a composition's own layers have a camera depth")
    return ctx.item(cur)
