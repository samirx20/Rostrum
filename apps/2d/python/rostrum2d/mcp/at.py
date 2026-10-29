"""look_at: what is at a point of the frame, from the evaluated values (no rendering). look_at (what: colour): the colour
there in the rendered frame (the export engine), and which layer is on top there."""
from __future__ import annotations

import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from rostrum2d import boxes, drawing, painted, painted_fill
from rostrum2d.frame import view as camera

from . import render, world_facts as wf
from .geometry import _apply, _invert, comp_size, covers, drawn_box, flatten, problems_showing
from .pick import ITEM_COMP, TIME, doc_and_comp, time_of

tools = Tools()
SHOWN = ("x", "y", "scale", "rotation", "opacity", "w", "h", "fill", "color", "size", "body", "start", "end")


POINT = {"x": {"type": "number", "description": "Pixels from the left of the composition."},
         "y": {"type": "number", "description": "Pixels from the top of the composition."}}


SPACE = {"space": {"type": "string", "enum": ["frame", "world"], "default": "frame",
                   "description": "frame: x, y are px of the picture (the export). world: x, y are world px, the canvas the frame moves over "
                                  "(what look_frame (what: world)'s ruler shows); boxes are where the world view draws each layer."}}


def _painted(doc, n: dict, x: float, y: float, t: float, frame: int, fps: float) -> dict | None:
    """Where the point lands in a painted fill's painting (painted.Mapping, the engine's layout): its px, folded into the
    painting on Tile; `on_painting` false in the bands Fit leaves empty; which drawing shows (1 = the first)."""
    p = n["props"]
    painting = next((q for q in doc.data.get("paintings", []) if q["id"] == p.get("fillPainting")), None)
    inv = _invert(n["matrix"])
    if p.get("fillType") != "painted" or painting is None or inv is None:
        return None
    m = painted.Mapping(p, painting, n["size"], t - p.get("start", 0.0))
    px, py = m.wrapped(*m.to_painting(*_apply(inv, x, y)))
    shown = painted_fill.shown(doc.item(n["id"]), painting, frame, fps)
    drawings = drawing.shown_frames(painting)
    return {"painting": painting["id"], "name": painting.get("name", ""), "at": [round(px, 1), round(py, 1)],
            "size": [m.pw, m.ph], "on_painting": 0 <= px + 0.5 <= m.pw and 0 <= py + 0.5 <= m.ph,
            "drawing": drawings.index(shown) + 1 if shown in drawings else 0}


def _said(f: dict | None) -> str:
    if not f:
        return ""
    where = f'at ({f["at"][0]:g}, {f["at"][1]:g}) of {f["size"][0]} × {f["size"][1]}' if f["on_painting"] else "outside it (an empty band)"
    return f', painted fill {f["name"]} {where}' + (f', drawing {f["drawing"]}' if f["drawing"] > 1 else "")


def _covering(nodes: list[dict], x: float, y: float) -> list[dict]:
    """The flattened layers whose box covers (x, y), top first."""
    return [n for n in reversed(nodes) if covers(n, x, y)]      # the last layer in the list is on top


def _pickable(n: dict, by_id: dict) -> bool:
    """A click on the canvas can pick this layer here (screen2d/bounds.py's list: boxes.can_pick, and not hidden, out of
    time or only a track matte, in it or in a group of it)."""
    chain = [by_id[g]["layer"] for g in n["within"]] + [n["layer"]]
    return (n["in_time"] and not n["matte_for"] and not any(c.get("hidden") for c in chain)
            and boxes.can_pick(n["paint"], n["opacity"], any(c.get("locked") for c in chain)))


@tools.tool("look_at", {"required": ["x", "y"], "properties": {**ITEM_COMP, **TIME, **POINT, **SPACE}})
def look_at(ctx, args):
    """What is at a point at a time: the layers whose painted part covers it (a drawing: a painted pixel or one within 3 canvas px, not its empty canvas), top first, with their values at that time and their box.
    `space` "frame" (default): x, y are composition pixels, the picture. "world": x, y are world px, the canvas around the frame
    (read them off look_frame (what: world)'s ruler); the reply says whether the point is inside the frame then. APPROXIMATE: boxes come from each layer's size and transform (text width is estimated);
    effects like glow and shadow, and masks, are not counted. Layers that are covered but invisible (opacity 0) are marked. Each row says `pickable`: a click on the canvas can pick it
    here (not hidden, locked, see-through, out of its time or only a track matte); the pickable rows in this order are what the
    screen's right-click › Select layer lists under the pointer (groups aside: it lists a group above its pieces).
    A layer with a painted fill says where the point lands in its painting (`painted_fill`: painting px, folded into the
    painting on Tile, and which drawing): paint.stroke {target: the painting, through: the layer} lands there."""
    doc, comp = doc_and_comp(ctx, args)
    t, frame = time_of(ctx, comp, args)
    x, y, (w, h) = args["x"], args["y"], comp_size(comp)
    world = args.get("space", "frame") == "world"
    rows = []
    nodes = flatten(comp, t, world)
    by_id = {n["id"]: n for n in nodes}
    for n in _covering(nodes, x, y):
        why = problems_showing(n, w, h, frame=not world)
        box = [round(v, 1) for v in drawn_box(n)]
        rows.append({"id": n["id"], "type": n["type"], "box": {"left": box[0], "top": box[1], "right": box[2], "bottom": box[3]},
                     "values": {k: n["props"][k] for k in SHOWN if k in n["props"]}, "visible": not why, "why_not_visible": why,
                     "inside": list(n["within"]), "pickable": _pickable(n, by_id), "painted_fill": _painted(doc, n, x, y, t, frame, comp.get("fps", 30))})
    inside = wf.point_in_frame(comp, t, x, y) if world else 0 <= x < w and 0 <= y < h
    lines = [f'{r["id"]} ({r["type"]}{_said(r["painted_fill"])}){"" if r["visible"] else " [not visible: " + ", ".join(r["why_not_visible"]) + "]"}'
             for r in rows]
    where = f"({x:g}, {y:g}) {'world px' if world else 'px'} at {t:.3f} s (frame {frame}){'' if inside else ', which is outside the frame'}"
    summary = f"At {where}: " + (f'{len(rows)} layer{"s" * (len(rows) != 1)}, top first: {"; ".join(lines)}.' if rows else "no layer's box covers it.")
    cam = camera.shot(comp, t)
    cam_says = f" Frame: x {cam.x:g}, y {cam.y:g}, zoom {cam.zoom:g}." if cam else ""
    return Reply(summary + " Approximate boxes." + cam_says,
                 {"time": t, "frame": frame, "point": [x, y], "space": "world" if world else "frame", "inside_frame": inside, "layers": rows,
                  "frame_at": {"x": cam.x, "y": cam.y, "zoom": cam.zoom, "rotation": cam.roll} if cam else None})


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
    scene = render.look_scene(doc, comp["id"], t)
    top = next((n for n in _covering(flatten(comp, t), x, y) if n["type"] != "group" and not problems_showing(n, w, h)), None)

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

    return ctx.long(f'look_at (what: colour) {comp["id"]} f{frame}', job_fn)
