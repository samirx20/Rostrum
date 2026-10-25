"""Painting on any element (UX_SPEC.md §3.8): `paint.stroke` paints one stroke on a shape, text, picture, path or
drawing, making what it needs on the way, in one change (one undo step):

- the drawing (`frame`) when the element has none at that frame, and the paint layer (`layer: "new"`, or the first
  stroke on a drawing that has none: paint layers are made by the first stroke);
- `paintW` × `paintH` at an element's first stroke, from its box (drawing.paint_size): the paint is then stretched
  over the box, so it moves, scales and turns with the element;
- on a drawing, a bigger canvas when the stroke reaches past it, in any direction (paint_grow.py), or past 8192 px a
  side a new drawing beside it that takes the stroke (paint_overflow.py).

Points are composition px (`space: "comp"`, the default: where the element is at `frame`) or the paint canvas's own
px (`space: "canvas"`, what look_drawing shows and what the screen's pen sends). A painting is painted in its own px,
or `through` a layer it fills (paint_through.py: painting in place). The stroke itself is the painting kit's (`build`),
so a scripted stroke and a painted one are the same item.
"""
from __future__ import annotations

import rostrum_paint
from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_paint.ops import build

from rostrum_paint import linked

from . import drawing as D, paint_fields, paint_grow, paint_overflow, paint_through, paintings, placement, shared_paints
from .engine import EngineError
from .evaluate import resolve
from .kind import REGISTRY as R

PAINTABLE = ("drawing", "painting", *paint_fields.TYPES)
MASK = next(p for p in rostrum_paint.FIELDS["stroke"] if p.name == "mask")


@R.operation("paint.stroke", "Paint one stroke on an element (shape, text, image, video, path) or a drawing. Its paint "
             "is the element's own look: kept inside its outline (Keep inside the outline), stretched over its box, moving "
             "with it. Makes the drawing at that frame and the paint layer if missing; several calls in one list are one "
             "undo step. A drawing layer grows to hold the stroke, in any direction, nothing painted moving on screen (its "
             "canvas px shift by the growth left / up); past 8192 px a side the stroke starts a new drawing just above it "
             "(\"<name> 2\"), in the same undo step. A painting (painted fill): its own px, or `through` a layer filled with it "
             "(the stroke goes through that layer's fit, scale, offset, rotation and drift into the painting, and shows on "
             "every layer using it; on Tile it carries on across tile edges; on a seamless painting a stroke that crosses the painting's edge comes back on the opposite side).", target=PAINTABLE, label="Paint",
             params=[Param.points("points", label="Path", min=2, max=5, required=True,
                                  help="[[x, y, pressure 0..1, tilt x°, tilt y°], …]; pressure 1 and no lean when "
                                       "left out (tilt: the pen's lean each way, -60..60)"),
                     Param.choice("space", ["comp", "canvas", "layer"], label="Points in", default="comp", importance="secondary",
                                  labels={"comp": "Composition px", "canvas": "Paint canvas px", "layer": "The layer's own px"},
                                  help="comp: where the element is at `frame`; canvas: the paint's own px (look_drawing's); "
                                       "layer (with `through`): the px of the layer's box, before its move, scale and turn"),
                     Param.id("through", label="Through layer", importance="secondary",
                              help="On a painting: a layer filled with it. The points are that layer's (comp or layer px) and "
                                   "go through its Fit, Scale, Offset, Rotation and Drift at `frame` into the painting, into "
                                   "the drawing it shows then; on Tile a stroke crossing a tile edge goes on in the next tile. "
                                   "Without it a painting's points are its own px"),
                     Param.text("layer", label="Paint layer", default="", importance="secondary",
                                help='"new" = a new paint layer on top (in every drawing of the layer); a paint layer '
                                     'id or its shared key (the same in every drawing); empty = the top unlocked one'),
                     Param.number("frame", label="Frame", min=0, max=10**7, integer=True, importance="secondary",
                                  help="Which frame's drawing (with Draw each frame on; otherwise the one painting). Default 0"),
                     Param.text("id", label="Stroke id", importance="deep", help="Optional; counted when left out"),
                     *rostrum_paint.BRUSH, MASK])
def paint_stroke(ctx, targets, args):
    brush = {k: v for k, v in args.items() if k not in ("points", "space", "layer", "frame", "id", "through")}
    if args.get("space") == "layer" and not args.get("through"):
        ctx.fail(codes.BAD_ARGUMENT, 'space "layer"', "needs `through`: the layer whose painted fill the stroke is painted on")
    for t in targets:
        item = ctx.item(t)
        n = args.get("frame", 0)
        pts, more = args["points"], []
        if args.get("through"):
            if item["type"] != "painting":
                ctx.fail(codes.BAD_ARGUMENT, f'"{t}"', "is not a painting: `through` paints a painting through a layer it fills")
            n, (pts, *more) = paint_through.stroke(ctx, t, args, brush, _fps(ctx, args["through"]), _place)
        elif item["type"] != "painting":                   # a painting has no place in the scene: its points are always its own px
            props = resolve(item, n / _fps(ctx, t))
            cw, ch = D.paint_size(item, props)
            if args.get("space", "comp") == "comp":     # where the engine draws the layer at that frame (placement.py)
                pts = placement.canvas_points(item, props, _place(ctx, t, n), pts)
        if item["type"] == "drawing":                   # the drawing grows to hold the stroke, or a new one starts
            t, pts = _fit(ctx, t, pts, {**rostrum_paint.brush_defaults(), **brush})
        if item["type"] not in D.CANVASES and not item.get("paintW"):
            ctx.set(t, "paintW", cw)
            ctx.set(t, "paintH", ch)
        frame = _frame(ctx, t, n)
        paint = _paint(ctx, frame, args.get("layer", ""))
        sid = args.get("id") if len(targets) == 1 and args.get("id") else ctx.new_id("stroke")
        if sid in ctx.idx:
            ctx.fail(codes.BAD_ARGUMENT, f'id "{sid}"', "is already used in this document")
        wrap = {"wrap": True} if paintings.seamless(item) else {}       # a seamless painting: it wraps (the kit's wrap.py)
        ctx.insert(paint["id"], "strokes", build("stroke", sid, {**brush, **wrap, "points": pts}, ctx.where))
        for piece in more:              # the same stroke in the other tiles it crossed into (paint_through.py)
            ctx.insert(paint["id"], "strokes", build("stroke", ctx.new_id("stroke"), {**brush, "points": piece}, ctx.where))


def _fit(ctx, t: str, pts, brush: dict) -> tuple[str, list]:
    """(the drawing the stroke goes on, its points there): `t` grown to hold it (paint_grow.py), or a new drawing beside
    it when `t` can't grow that far (paint_overflow.py). An eraser never grows it: past the edge there is nothing to
    take away (it grew the box and moved the anchor for nothing)."""
    item = ctx.item(t)
    if brush.get("mode") == "erase":
        return t, pts
    box = paint_grow.reach(pts, brush)
    if paint_grow.fits(int(item.get("w", 1920)), int(item.get("h", 1080)), box):
        dx, dy = paint_grow.grow(ctx, t, box)
        return t, paint_grow.shifted(pts, dx, dy) if dx or dy else pts
    return paint_overflow.start(ctx, t, box, pts)


def _place(ctx, id_: str, n: int) -> dict:
    """The layer's place at frame n (placement.place_at: through its groups, the camera and tilt), loudly."""
    try:
        return placement.place_at(ctx.doc, id_, n / _fps(ctx, id_))
    except (KeyError, ValueError, EngineError) as e:
        ctx.fail(codes.BAD_ARGUMENT, f'"{id_}" at frame {n}', f"has no place to paint in composition px: {e}",
                 hint='Pass points in the paint canvas px (space "canvas").')


def _fps(ctx, id_) -> float:
    cur = id_
    while ctx.item(cur).get("type") != "comp":
        cur = ctx.idx[cur].parent
    return ctx.item(cur).get("fps", 30)


def _frame(ctx, t: str, n: int) -> dict:
    """The drawing the stroke goes on: the one shown at frame n (the Draw each frame rule), made blank if none is."""
    item = ctx.item(t)
    here = D.frame_at(item, n) if D.each_frame(item) else (item.get("frames") or [None])[0]
    if here is not None:
        return here
    at = n if D.each_frame(item) else 0
    frame = shared_paints.blank_frame(ctx, item, at) if item.get("frames") else         {"id": ctx.new_id("frame"), "type": "frame", "at": at, "paints": [], "paintmasks": []}
    ctx.insert(t, "frames", frame, sum(1 for f in item.get("frames", []) if f["at"] < at))
    return ctx.item(frame["id"])


def _paint(ctx, frame: dict, layer: str) -> dict:
    paints = frame["paints"]
    if layer and layer != "new":
        found = next((p for p in paints if layer in (p["id"], linked.key(p))), None)
        if found is None:
            ctx.fail(codes.NOT_FOUND, f'layer "{layer}"', f'is not a paint layer of drawing {frame["id"]}',
                     ["new", *(p["id"] for p in paints)])
        if found.get("locked"):
            ctx.fail(codes.CONFLICT, f'layer "{layer}"', "is locked", hint="paint.unlock it first",
                     plain=f'"{found["name"]}" is locked. Turn off its Lock to paint on it.' if found.get("name")
                     else "That paint layer is locked. Turn off its Lock to paint on it.")
        return found
    top = next((p for p in reversed(paints) if not p.get("locked")), None)
    if top is not None and layer != "new":
        return top
    if paints and layer != "new":
        ctx.fail(codes.CONFLICT, f'drawing {frame["id"]}', "has only locked paint layers",
                 hint='Unlock one (paint.unlock) or paint with layer: "new".',
                 plain="Every paint layer on this drawing is locked. Turn off a Lock to paint on it, or add a new paint layer.")
    paint = build("paint", ctx.new_id("paint"), {"name": "Paint" if not paints else f"Paint {len(paints) + 1}"}, ctx.where)
    shared_paints.add(ctx, frame["id"], paint)
    return ctx.item(paint["id"])
