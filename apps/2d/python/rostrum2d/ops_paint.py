"""Painting on any element (UX_SPEC.md §3.8): `paint.stroke` paints one stroke on a shape, text, picture, path or
drawing, making what it needs on the way, in one change (one undo step):

- the drawing (`frame`) when the element has none at that frame, and the paint layer (`layer: "new"`, or the first
  stroke on a drawing that has none: paint layers are made by the first stroke);
- `paintW` × `paintH` at an element's first stroke, from its box (drawing.paint_size): the paint is then stretched
  over the box, so it moves, scales and turns with the element.

Points are composition px (`space: "comp"`, the default: where the element is at `frame`) or the paint canvas's own
px (`space: "canvas"`, what look_drawing shows and what the screen's pen sends). The stroke itself is the painting
kit's (`build`), so a scripted stroke and a painted one are the same item.
"""
from __future__ import annotations

import rostrum_paint
from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_paint.ops import build

from . import drawing as D, paint_fields, placement
from .engine import EngineError
from .evaluate import resolve
from .kind import REGISTRY as R

PAINTABLE = ("drawing", *paint_fields.TYPES)
MASK = next(p for p in rostrum_paint.FIELDS["stroke"] if p.name == "mask")


@R.operation("paint.stroke", "Paint one stroke on an element (shape, text, image, video, path) or a drawing. Its paint "
             "is the element's own look: kept inside its outline (Keep inside the outline), stretched over its box, moving "
             "with it. Makes the drawing at that frame and the paint layer if missing; several calls in one list are one "
             "undo step.", target=PAINTABLE, label="Paint",
             params=[Param.points("points", label="Path", min=2, max=5, required=True,
                                  help="[[x, y, pressure 0..1, tilt x°, tilt y°], …]; pressure 1 and no lean when "
                                       "left out (tilt: the pen's lean each way, -60..60)"),
                     Param.choice("space", ["comp", "canvas"], label="Points in", default="comp", importance="secondary",
                                  labels={"comp": "Composition px", "canvas": "Paint canvas px"},
                                  help="comp: where the element is at `frame`; canvas: the paint's own px (look_drawing's)"),
                     Param.text("layer", label="Paint layer", default="", importance="secondary",
                                help='"new" = a new paint layer on top; a paint layer id; empty = the top unlocked one'),
                     Param.number("frame", label="Frame", min=0, max=10**7, integer=True, importance="secondary",
                                  help="Which frame's drawing (with Draw each frame on; otherwise the one painting). Default 0"),
                     Param.text("id", label="Stroke id", importance="deep", help="Optional; counted when left out"),
                     *rostrum_paint.BRUSH, MASK])
def paint_stroke(ctx, targets, args):
    brush = {k: v for k, v in args.items() if k not in ("points", "space", "layer", "frame", "id")}
    for t in targets:
        item = ctx.item(t)
        n = args.get("frame", 0)
        props = resolve(item, n / _fps(ctx, t))
        cw, ch = D.paint_size(item, props)
        pts = args["points"]
        if args.get("space", "comp") == "comp":         # where the engine draws the layer at that frame (placement.py)
            pts = placement.canvas_points(item, props, _place(ctx, t, n), pts)
        if item["type"] != "drawing" and not item.get("paintW"):
            ctx.set(t, "paintW", cw)
            ctx.set(t, "paintH", ch)
        frame = _frame(ctx, t, n)
        paint = _paint(ctx, frame, args.get("layer", ""))
        sid = args.get("id") if len(targets) == 1 and args.get("id") else ctx.new_id("stroke")
        if sid in ctx.idx:
            ctx.fail(codes.BAD_ARGUMENT, f'id "{sid}"', "is already used in this document")
        ctx.insert(paint["id"], "strokes", build("stroke", sid, {**brush, "points": pts}, ctx.where))


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
    frame = {"id": ctx.new_id("frame"), "type": "frame", "at": at, "paints": [], "paintmasks": []}
    ctx.insert(t, "frames", frame, sum(1 for f in item.get("frames", []) if f["at"] < at))
    return ctx.item(frame["id"])


def _paint(ctx, frame: dict, layer: str) -> dict:
    paints = frame["paints"]
    if layer and layer != "new":
        found = next((p for p in paints if p["id"] == layer), None)
        if found is None:
            ctx.fail(codes.NOT_FOUND, f'layer "{layer}"', f'is not a paint layer of drawing {frame["id"]}',
                     ["new", *(p["id"] for p in paints)])
        if found.get("locked"):
            ctx.fail(codes.CONFLICT, f'layer "{layer}"', "is locked", hint="paint.unlock it first")
        return found
    top = next((p for p in reversed(paints) if not p.get("locked")), None)
    if top is not None and layer != "new":
        return top
    if paints and layer != "new":
        ctx.fail(codes.CONFLICT, f'drawing {frame["id"]}', "has only locked paint layers",
                 hint='Unlock one (paint.unlock) or paint with layer: "new".')
    paint = build("paint", ctx.new_id("paint"), {"name": "Paint" if not paints else f"Paint {len(paints) + 1}"}, ctx.where)
    ctx.insert(frame["id"], "paints", paint)
    return ctx.item(paint["id"])
