"""look_at: what is at a point of the frame, from the evaluated values (no rendering)."""
from __future__ import annotations

from rostrum_core.mcp import Reply, Tools

from rostrum2d.camera import view as camera

from .geometry import comp_size, covers, drawn_box, flatten, problems_showing
from .pick import ITEM_COMP, TIME, doc_and_comp, time_of

tools = Tools()
SHOWN = ("x", "y", "scale", "rotation", "opacity", "w", "h", "fill", "color", "size", "body", "start", "end")


@tools.tool("look_at", {"required": ["x", "y"], "properties": {**ITEM_COMP, **TIME, "x": {"type": "number", "description": "Pixels from the left of the composition."},
                                                              "y": {"type": "number", "description": "Pixels from the top of the composition."}}})
def look_at(ctx, args):
    """What is at a point (x, y in composition pixels) at a time: the layers whose box covers it, top first, with their values
    at that time and their box. APPROXIMATE: boxes come from each layer's size and transform (text width is estimated);
    effects like glow and shadow, and masks, are not counted. Layers that are covered but invisible (opacity 0) are marked."""
    doc, comp = doc_and_comp(ctx, args)
    t, frame = time_of(ctx, comp, args)
    x, y, (w, h) = args["x"], args["y"], comp_size(comp)
    rows = []
    for n in reversed(flatten(comp, t)):                    # the last layer in the list is on top
        if not covers(n, x, y):
            continue
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
    cam_says = f" Camera: x {cam[0]:g}, y {cam[1]:g}, zoom {cam[2]:g}." if cam else " No camera."
    return Reply(summary + " Approximate boxes." + cam_says,
                 {"time": t, "frame": frame, "point": [x, y], "inside_frame": inside, "layers": rows,
                  "camera": {"x": cam[0], "y": cam[1], "zoom": cam[2]} if cam else None})
