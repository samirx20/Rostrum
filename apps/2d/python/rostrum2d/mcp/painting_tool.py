"""Paintings for agents (paintings.py): see one and read what it is and where it is used.

    look_painting {painting, repeats?, frame?, zoom?, grid?, sampling?, paint?, width?}   alone in its own px, or 3 × 3
    inspect_painting {painting}                                    size, Seamless, layers, drawings, every use, seam check

`look_drawing`, `inspect_drawing_at`, `inspect_stroke_landed` and `look_drawing_change` also take a painting's id (its px
are the canvas's). Making and changing one: painting.add / painting.set / painting.duplicate / painting.remove, strokes
with paint.stroke or stroke.add on its drawings, using it with layer.fill {type: "painted"}. Painting it where a layer
shows it: paint.stroke {target: the painting, through: the layer, space: "layer" or "comp"}; look_at says where a point
lands in the painting.
"""
from __future__ import annotations

import numpy as np
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_core.mcp.files import look_path
from rostrum_paint import canvas, see

from rostrum2d import drawing as D, paintings
from . import draw

tools = Tools()
PAINTING = {"painting": {"type": "string", "description": "A painting's id (inspect_painting lists them)."}}


def _painting(ctx, doc, painting: str) -> dict:
    have = paintings.all_of(doc.data)
    found = next((p for p in have if p["id"] == painting), None)
    if found is None:
        raise RostrumError.not_found(ctx.tool, "painting", painting, [p["id"] for p in have], "this document's paintings")
    return found


@tools.tool("look_painting", {"required": ["painting"], "properties": {
    **draw.ITEM, **PAINTING, "frame": draw.FRAME["frame"], **draw.ZOOM, **draw.GRID, **draw.SAMPLING,
    "paint": {"type": "string", "description": "Show only this paint layer of the drawing (its id). Default: all together."},
    "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 1200, "description": "Picture width in px."},
    "repeats": {"type": "integer", "enum": [0, 1], "default": 0,
                "description": "1: the painting with its repeats all round (3 × 3, the outer ones a little darker), to judge "
                               "whether its edges meet (a seamless painting's do)."}}})
def look_painting(ctx, args):
    """A painting, in its own pixels: the drawing shown at a frame number (a painting that draws each frame loops), optionally zoomed,
    with a labelled pixel grid or one paint layer alone; or with `repeats` 1 its repeats all round, to see seams. Transparent
    paper shows as a checkerboard."""
    doc = ctx.document(args.get("item"))
    p = _painting(ctx, doc, args["painting"])
    if not args.get("repeats"):
        return draw.look_drawing(ctx, {**{k: v for k, v in args.items() if k != "painting"}, "layer": args["painting"]})
    n = args.get("frame", 0)
    frame = draw.frame_of(ctx, p, n)
    w, h = D.canvas_size(p)
    one = canvas.layer_rgba(frame, args["paint"], w, h) if args.get("paint") else canvas.rgba8(frame, w, h)
    grid = np.tile(one, (3, 3, 1))
    dim = np.ones((3 * h, 3 * w, 1), np.float32) * 0.78
    dim[h:2 * h, w:2 * w] = 1
    grid[..., :3] = (grid[..., :3] * dim).astype(np.uint8)
    note = f'{p["id"]} with its repeats (the middle one is the painting, from ({w}, {h}) in this picture)'
    try:
        pic = see.view(grid, args.get("zoom"), args.get("grid"), args.get("width", 1200), label=note,
                       sampling=args.get("sampling", "auto"))
    except ValueError as e:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"zoom", "width" or "sampling"', str(e)) from e
    dest = look_path(f'{doc.item_id or "doc"}_{p["id"]}_f{n}_repeats')
    pic.save(dest)
    said = "; ".join(paintings.seams(one))
    return Reply(f'{p["id"]} at frame {n} with its repeats all round ({w}×{h} each): {said}.',
                 {"painting": p["id"], "frame_item": frame["id"], "canvas": [w, h], "seamless": bool(p.get("seamless")),
                  "seams": paintings.seams(one), "picture": [pic.width, pic.height]}, [dest], [dest])


@tools.tool("inspect_painting", {"properties": {**draw.ITEM, "painting": {"type": "string", "description": "A painting's id. Left out: every painting of the document."}}})
def inspect_painting(ctx, args):
    """Each painting: its size, Seamless, paint layers, drawings (and holds), every layer using it with how it sits
    (fit, scale, offset, rotation, drift, colour under it, opacity), and a seam check of its first drawing in words
    ("left and right edges meet: no seam"; "top and bottom differ by 14 %: seam at y = 0"). To paint it where one of those layers shows it:
    paint.stroke {target: the painting, through: that layer, space: "layer" (its box px) or "comp"}."""
    doc = ctx.document(args.get("item"))
    chosen = [_painting(ctx, doc, args["painting"])] if args.get("painting") else paintings.all_of(doc.data)
    rows, lines = [], []
    for p in chosen:
        frames = p.get("frames", [])
        layers = [{"id": q["id"], "name": q.get("name"), "mode": q.get("mode"), "opacity": q.get("opacity"), "locked": bool(q.get("locked")),
                   "strokes": len(q.get("strokes", []))} for q in (frames[0]["paints"] if frames else [])]
        drawings = [{"id": f["id"], "at": f["at"], "strokes": draw.stroke_count(f)} for f in D.shown_frames(p)] if frames else []
        used = [{"layer": u["id"], "fit": u.get("fillFit", "fill"), "scale": u.get("fillScale", 1.0),
                 "offset": [u.get("fillOffsetX", 0.0), u.get("fillOffsetY", 0.0)], "rotation": u.get("fillRotation", 0.0),
                 "drift": [u.get("fillDriftX", 0.0), u.get("fillDriftY", 0.0)], "under": u.get("fillUnder"), "blend": u.get("fillBlend", "normal"),
                 "opacity": u.get("fillOpacity", 1.0), "phase": u.get("fillPhase", 0)} for u in paintings.uses(doc.data, p["id"])]
        seam = paintings.seams(canvas.rgba8(frames[0], *D.canvas_size(p))) if frames else []
        rows.append({"id": p["id"], "name": p.get("name"), "size": [p["w"], p["h"]], "seamless": bool(p.get("seamless")),
                     "each_frame": D.each_frame(p), "loop": p.get("loop", "loop"), "paint_layers": layers, "drawings": drawings,
                     "uses": used, "seams": seam})
        lines.append(f'{p["id"]} "{p.get("name")}": {p["w"]}×{p["h"]}' + (", seamless" if p.get("seamless") else "")
                     + f', {len(layers)} paint layer(s), {len(drawings)} drawing(s), used by {len(used)} layer(s)'
                     + (f' ({", ".join(u["layer"] for u in used)})' if used else "") + (f'; {"; ".join(seam)}' if seam else ""))
    return Reply("\n".join(lines) if lines else "This document has no paintings (make one with painting.add).", {"paintings": rows})
