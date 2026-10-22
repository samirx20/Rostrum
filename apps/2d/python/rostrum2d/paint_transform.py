"""`stroke.transform` (UX_SPEC.md §3.8, "Select and move paint"): move, scale and turn strokes and fills by numbers, in
one change (one undo step). The screen's box, corner handles and turn knob record this very call when they are let go
(screen2d/stroke_select.py, stroke_handles.py), so a dragged turn and an agent's typed one leave the same step.

The strokes are scaled by `scale` and turned by `turn` degrees (clockwise on screen) about `around` (default: the
centre of their box), then moved by `dx, dy`. In composition px (`space: "comp"`, the default) this happens where the
strokes are seen at `frame`, through the layer's own place (placement.py, the pen's mapping), so a turn looks like a
turn however the layer is stretched or tilted; `space: "canvas"` works in the paint canvas's own px. A stroke's brush
size follows the scale; a fill (an outline) has none.
"""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.errors import codes

from . import drawing as D, placement
from .evaluate import resolve
from .kind import REGISTRY as R
from .ops_paint import _fps, _place


def moved(points: list, dx: float, dy: float) -> list:
    return [[p[0] + dx, p[1] + dy, *p[2:]] for p in points]


def transformed(points: list, around: tuple[float, float], scale: float = 1.0, turn: float = 0.0) -> list:
    """The points scaled by `scale` and turned by `turn` degrees (clockwise on screen) about `around`."""
    ax, ay = around
    c, s = math.cos(math.radians(turn)), math.sin(math.radians(turn))
    out = []
    for p in points:
        x, y = (p[0] - ax) * scale, (p[1] - ay) * scale
        out.append([ax + x * c - y * s, ay + x * s + y * c, *p[2:]])
    return out


def centre(groups: list[list]) -> tuple[float, float]:
    """The centre of the box around all the points of all the strokes."""
    xs, ys = [p[0] for g in groups for p in g], [p[1] for g in groups for p in g]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


@R.operation("stroke.transform", "Move, scale and turn strokes and fills by numbers, in one step: scaled and turned "
             "about `around` (default the centre of their box), then moved. Composition px by default (where they are "
             "seen at `frame`); a stroke's brush size follows the scale.", target=("stroke", "fill"), label="Transform strokes",
             params=[Param.number("dx", label="Move right", default=0, help="px; negative = left"),
                     Param.number("dy", label="Move down", default=0, help="px; negative = up"),
                     Param.number("scale", label="Scale", default=1, min=0.001, max=1000, step=0.01, help="1 = as is"),
                     Param.number("turn", label="Turn", default=0, min=-3600, max=3600, help="degrees, clockwise on screen"),
                     Param.points("around", label="Turn about", min=2, max=2, importance="secondary",
                                  help="[[x, y]]; default: the centre of the strokes' box"),
                     Param.choice("space", ["comp", "canvas"], label="Numbers in", default="comp", importance="secondary",
                                  labels={"comp": "Composition px", "canvas": "Paint canvas px"}),
                     Param.number("frame", label="Frame", min=0, max=10**7, integer=True, importance="secondary",
                                  help="Where the strokes are seen (comp px). Default: their drawing's frame")])
def stroke_transform(ctx, targets, args):
    comp = args.get("space", "comp") == "comp"
    maps, pts = {}, {}
    for t in targets:
        owner, at = _owner(ctx, t)
        if comp and owner not in maps:
            n = args.get("frame", at)
            item = ctx.item(owner)
            maps[owner] = (item, resolve(item, n / _fps(ctx, owner)), _place(ctx, owner, n))
        p = ctx.item(t)["points"]
        pts[t] = placement.comp_points(*maps[owner], p) if comp else p
    around = tuple(args["around"][0][:2]) if args.get("around") else centre(list(pts.values()))
    k, turn = args.get("scale", 1), args.get("turn", 0)
    for t in targets:
        new = moved(transformed(pts[t], around, k, turn), args.get("dx", 0), args.get("dy", 0))
        if comp:
            new = placement.canvas_points(*maps[_owner(ctx, t)[0]], new)
        ctx.set(t, "points", new)
        item = ctx.item(t)
        if k != 1 and item["type"] == "stroke":
            ctx.set(t, "size", round(item["size"] * k, 3))


def _owner(ctx, stroke_id: str) -> tuple[str, int]:
    """(the element or drawing the stroke is painted on, the frame its drawing is at)."""
    frame = ctx.idx[ctx.idx[stroke_id].parent].parent           # stroke -> paint layer -> frame
    if ctx.item(frame).get("type") != "frame":
        ctx.fail(codes.BAD_ARGUMENT, f'"{stroke_id}"', "is not painted on an element or a drawing")
    owner = ctx.idx[frame].parent
    return owner, ctx.item(frame).get("at", 0) if D.each_frame(ctx.item(owner)) else 0
