"""Paintings for agents (paintings.py): see one and read what it is and where it is used.

    look_painting {painting, drawing?, zoom?, grid?, sampling?, paint?, width?}   the painting alone, in its own px
    inspect_painting {painting}                                                    size, Seamless, layers, drawings, every use

`look_drawing`, `inspect_drawing_at`, `inspect_stroke_landed` and `look_drawing_change` also take a painting's id (its px
are the canvas's). Making and changing one: painting.add / painting.set / painting.duplicate / painting.remove, strokes
with paint.stroke or stroke.add on its drawings, using it with layer.fill {type: "painted"}.
"""
from __future__ import annotations

from rostrum_core.errors import RostrumError
from rostrum_core.mcp import Reply, Tools

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
    "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 1200, "description": "Picture width in px."}}})
def look_painting(ctx, args):
    """A painting, in its own pixels: the drawing shown at a frame number (a painting that draws each frame loops), optionally zoomed,
    with a labelled pixel grid or one paint layer alone. Transparent paper shows as a checkerboard."""
    doc = ctx.document(args.get("item"))
    _painting(ctx, doc, args["painting"])
    return draw.look_drawing(ctx, {**{k: v for k, v in args.items() if k != "painting"}, "layer": args["painting"]})


@tools.tool("inspect_painting", {"properties": {**draw.ITEM, "painting": {"type": "string", "description": "A painting's id. Left out: every painting of the document."}}})
def inspect_painting(ctx, args):
    """Each painting: its size, Seamless, paint layers, drawings (and holds), and every layer using it with how it sits
    (fit, scale, offset, rotation, drift, colour under it, opacity)."""
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
        rows.append({"id": p["id"], "name": p.get("name"), "size": [p["w"], p["h"]], "seamless": bool(p.get("seamless")),
                     "each_frame": D.each_frame(p), "loop": p.get("loop", "loop"), "paint_layers": layers, "drawings": drawings, "uses": used})
        lines.append(f'{p["id"]} "{p.get("name")}": {p["w"]}×{p["h"]}' + (", seamless" if p.get("seamless") else "")
                     + f', {len(layers)} paint layer(s), {len(drawings)} drawing(s), used by {len(used)} layer(s)'
                     + (f' ({", ".join(u["layer"] for u in used)})' if used else ""))
    return Reply("\n".join(lines) if lines else "This document has no paintings (make one with painting.add).", {"paintings": rows})
