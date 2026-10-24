"""look_at: what is at a point of the frame, from the evaluated values (no rendering). inspect_colour_at: the colour
there in the rendered frame (the export engine), and which layer is on top there."""
from __future__ import annotations

import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from rostrum2d.frame import view as camera

from . import render
from .geometry import comp_size, covers, drawn_box, flatten, problems_showing
from .pick import ITEM_COMP, TIME, doc_and_comp, time_of

tools = Tools()
SHOWN = ("x", "y", "scale", "rotation", "opacity", "w", "h", "fill", "color", "size", "body", "start", "end")


POINT = {"x": {"type": "number", "description": "Pixels from the left of the composition."},
         "y": {"type": "number", "description": "Pixels from the top of the composition."}}


def _covering(comp: dict, t: float, x: float, y: float) -> list[dict]:
    """The flattened layers whose box covers (x, y) at t, top first."""
    return [n for n in reversed(flatten(comp, t)) if covers(n, x, y)]      # the last layer in the list is on top


@tools.tool("look_at", {"required": ["x", "y"], "properties": {**ITEM_COMP, **TIME, **POINT}})
def look_at(ctx, args):
    """What is at a point (x, y in composition pixels) at a time: the layers whose box covers it, top first, with their values
    at that time and their box. APPROXIMATE: boxes come from each layer's size and transform (text width is estimated);
    effects like glow and shadow, and masks, are not counted. Layers that are covered but invisible (opacity 0) are marked."""
    doc, comp = doc_and_comp(ctx, args)
    t, frame = time_of(ctx, comp, args)
    x, y, (w, h) = args["x"], args["y"], comp_size(comp)
    rows = []
    for n in _covering(comp, t, x, y):
        why = problems_showing(n, w, h)
        box = [round(v, 1) for v in drawn_box(n)]
        rows.append({"id": n["id"], "type": n["type"], "box": {"left": box[0], "top": box[1], "right": box[2], "bottom": box[3]},
                     "values": {k: n["props"][k] for k in SHOWN if k in n["props"]}, "visible": not why, "why_not_visible": why,
                     "inside": list(n["within"])})
    inside = 0 <= x < w and 0 <= y < h
    lines = [f'{r["id"]} ({r["type"]}){"" if r["visible"] else " [not visible: " + ", ".join(r["why_not_visible"]) + "]"}' for r in rows]
    where = f"({x:g}, {y:g}) px at {t:.3f} s (frame {frame}){'' if inside else ', which is outside the frame'}"
    summary = f"At {where}: " + (f'{len(rows)} layer{"s" * (len(rows) != 1)}, top first: {"; ".join(lines)}.' if rows else "no layer's box covers it.")
    cam = camera.shot(comp, t)
    cam_says = f" Frame: x {cam.x:g}, y {cam.y:g}, zoom {cam.zoom:g}." if cam else ""
    return Reply(summary + " Approximate boxes." + cam_says,
                 {"time": t, "frame": frame, "point": [x, y], "inside_frame": inside, "layers": rows,
                  "frame": {"x": cam.x, "y": cam.y, "zoom": cam.zoom, "rotation": cam.roll} if cam else None})


@tools.tool("inspect_colour_at", {"required": ["x", "y"], "properties": {**ITEM_COMP, **TIME, **POINT}})
def inspect_colour_at(ctx, args):
    """The colour at a point (x, y in composition pixels) of the rendered frame at a time: its hex and opacity, read
    from the picture the export engine draws (every effect, mask and blend counted), and the layer on top there
    (approximate: from boxes, as look_at). Read-only: nothing in the document changes. The colour picker's eyedropper
    for agents."""
    doc, comp = doc_and_comp(ctx, args)
    t, frame = time_of(ctx, comp, args)
    x, y, (w, h) = args["x"], args["y"], comp_size(comp)
    if not (0 <= x < w and 0 <= y < h):
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"point ({x:g}, {y:g})", f"is outside the frame ({w}×{h} px)")
    scene = render.scene_of(doc, comp["id"], (t, t))
    top = next((n for n in _covering(comp, t, x, y) if n["type"] != "group" and not problems_showing(n, w, h)), None)

    def job_fn(job):
        from PIL import Image
        with tempfile.TemporaryDirectory(prefix="rostrum_pick_") as tmp:
            raw = Path(tmp) / "raw.png"
            render.stills(ctx.tool, scene, [(t, raw)])
            with Image.open(raw) as im:
                sx, sy = int(x * im.width / w), int(y * im.height / h)     # the engine's picture may be scaled
                r, g, b, a = im.convert("RGBA").getpixel((min(sx, im.width - 1), min(sy, im.height - 1)))
        hexc, alpha = f"#{r:02x}{g:02x}{b:02x}", round(a / 255, 3)
        layer = {"id": top["id"], "type": top["type"]} if top else None
        on = f'{top["id"]} ({top["type"]}) is on top there' if top else "no layer's box covers it (the background)"
        return Reply(f"At ({x:g}, {y:g}) px, {t:.3f} s (frame {frame}): {hexc}, opacity {round(alpha * 100)} %; {on}.",
                     {"time": t, "frame": frame, "point": [x, y], "color": hexc, "opacity": alpha, "layer": layer},
                     warnings=scene.get("warnings", []))

    return ctx.long(f'inspect_colour_at {comp["id"]} f{frame}', job_fn)
