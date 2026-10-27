"""Fill (UX_SPEC.md §3.8, "Eraser, colour picking and fill"): `paint.fill` fills the closed area around a point of an
element's painting with one colour, on the current paint layer, in one change (one undo step).

The edges are found in **all** the element's visible paint layers at that frame (so a colour layer fills up to the
lines on the line layer), or only in the paint layer filled (`edges: "layer"`); a locked paint layer refuses a fill; `gap` (Close gaps: small, medium, large) closes lines that don't quite meet. The result is
a painting-kit **fill** item, kept as its outline (rostrum_paint.fill): it stays sharp and replays like a stroke, on
the same render path (the kit's canvas PNG the engine draws), so the preview and the export are the same.
A click on a line, or in an area that is not closed, is refused with what to do instead; nothing is filled. On a
seamless painting the edges are joined: an area closed only across them is closed (rostrum_paint.fill, `wrap`).
"""
from __future__ import annotations

import numpy as np
from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_paint import canvas
from rostrum_paint.fill import GAPS, NotClosed, region
from rostrum_paint.fields import FIELDS
from rostrum_paint.ops import build

from . import drawing as D, paintings, placement
from .evaluate import resolve
from .kind import REGISTRY as R
from .ops_paint import PAINTABLE, _fps, _paint, _place

COLOUR = next(p for p in FIELDS["fill"] if p.name == "color")
OPACITY = next(p for p in FIELDS["fill"] if p.name == "opacity")


@R.operation("paint.fill", "Fill the closed area around a point of an element's painting (a drawing, or a painted "
             "shape, text, picture or path) with one colour, on its current paint layer. Edges come from all its visible "
             "paint layers (or only that layer's: edges \"layer\"); gap closes lines that don't quite meet. Kept as a sharp outline (a fill item). Refused when "
             "the point is on a line or its area is not closed.", target=PAINTABLE, label="Fill",
             params=[Param.points("at", label="Point", min=2, max=2, required=True,
                                  help="[[x, y]]: one point inside the area"),
                     Param.choice("space", ["comp", "canvas"], label="Point in", default="comp", importance="secondary",
                                  labels={"comp": "Composition px", "canvas": "Paint canvas px"}),
                     Param.choice("gap", list(GAPS), label="Close gaps", default="small",
                                  help="How far apart line ends may be and still close the area"),
                     COLOUR, OPACITY,
                     Param.text("layer", label="Paint layer", default="", importance="secondary",
                                help='A paint layer id; "new" = a new paint layer on top; empty = the top unlocked one'),
                     Param.choice("edges", ["all", "layer"], label="Edges from", default="all", importance="secondary",
                                  labels={"all": "All paint layers", "layer": "This layer"},
                                  help="all: the lines of every visible paint layer (fill Colour up to Ink's lines); "
                                       "layer: only the paint layer's own"),
                     Param.number("frame", label="Frame", min=0, max=10**7, integer=True, importance="secondary",
                                  help="Which frame's drawing (with Draw each frame on). Default 0"),
                     Param.text("id", label="Fill id", importance="deep", help="Optional; counted when left out")])
def paint_fill(ctx, targets, args):
    for t in targets:
        item = ctx.item(t)
        n = args.get("frame", 0)
        frame = D.frame_at(item, n) if D.each_frame(item) else (item.get("frames") or [None])[0]
        if frame is None or not any(p.get("strokes") for p in frame.get("paints", [])):
            ctx.fail(codes.CONFLICT, f'"{t}"', f"has no painting to fill at frame {n}",
                     hint="Draw closed lines first (paint.stroke), then fill inside them.")
        x, y = args["at"][0][:2]
        if args.get("space", "comp") == "comp":           # where the engine draws the layer at that frame, as paint.stroke
            x, y = placement.canvas_points(item, resolve(item, n / _fps(ctx, t)), _place(ctx, t, n), [[x, y]])[0][:2]
        w, h = D.canvas_size(item)
        paint = _paint(ctx, frame, args.get("layer", ""))
        only = paint["id"] if args.get("edges") == "layer" else None
        try:
            outline = region(_edges(frame, w, h, only), (x, y), args.get("gap", "small"), paintings.seamless(item))
        except NotClosed as e:
            ctx.fail(codes.BAD_ARGUMENT, f'at {args["at"][0]}', f"has nothing to fill: {e}",
                     hint="Click inside an area closed by lines, or try a larger gap.",
                     plain=e.plain or "There is nothing to fill there. Click inside an area closed by lines.")
        fid = args.get("id") if len(targets) == 1 and args.get("id") else ctx.new_id("fill")
        if fid in ctx.idx:
            ctx.fail(codes.BAD_ARGUMENT, f'id "{fid}"', "is already used in this document")
        values = {k: args[k] for k in ("color", "opacity") if k in args}
        ctx.insert(paint["id"], "strokes", build("fill", fid, {**values, "points": outline}, ctx.where))


def _edges(frame: dict, w: int, h: int, only: str | None = None) -> np.ndarray:
    """HxW 0..1: the most paint any visible paint layer (or only the one `only`) has at each pixel (each layer's own,
    whatever its blend). A toned layer (`ground`) covers every pixel, so it bounds nothing: it counts only when named."""
    alpha = np.zeros((h, w), np.float32)
    for p in frame.get("paints", []):
        if p.get("visible", True) and p.get("strokes") and (only == p["id"] or only is None and not p.get("ground")):
            np.maximum(alpha, canvas.layer_rgba(frame, p["id"], w, h)[..., 3] / np.float32(255), out=alpha)
    return alpha
