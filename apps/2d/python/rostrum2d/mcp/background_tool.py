"""Painted backgrounds: look_background (a big canvas in tiles, with what the camera sees of it) and inspect_background
(the depth layers, how far each moves, and whether each covers everything the camera shows of it). The maths is
background.py; painting is the kit's stroke.add, looking close is look_drawing.

Every coordinate here is a canvas pixel of the drawing layer, never a composition pixel.
"""
from __future__ import annotations

import math
import string

from PIL import ImageDraw
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_core.mcp.files import look_path
from rostrum_paint import canvas, see

from .. import background as B, drawing as D
from .draw import FRAME, ITEM, LAYER, SAMPLING, drawing_of, frame_of, stroke_count
from .pick import ITEM_COMP, doc_and_comp

tools = Tools()
CAM = (255, 200, 40)
TILE = (90, 200, 255)


def tile_boxes(w: int, h: int, cols: int, rows: int) -> dict[str, tuple[int, int, int, int]]:
    """{"A1": (x0, y0, x1, y1), …}: columns A, B … left to right, rows 1, 2 … top to bottom."""
    out = {}
    for r in range(rows):
        for c in range(cols):
            out[f"{string.ascii_uppercase[c]}{r + 1}"] = (round(c * w / cols), round(r * h / rows), round((c + 1) * w / cols), round((r + 1) * h / rows))
    return out


def _comp_holding(doc, layer_id):
    parent = doc.item(doc.parent_of(layer_id)[0])
    return parent if parent.get("type") == "comp" else None


def _frame_boxes(comp, layer):
    """The camera's frame at the first and last frame and everything it shows over the shot, in the layer's canvas px."""
    w, h = B.comp_size(comp)
    shots = B.shots(comp)
    out = {}
    for name, sl in (("start", shots[:1]), ("end", shots[-1:]), ("all", shots)):
        x0, y0, x1, y1 = B.seen_box(comp, layer.get("depth", 0.0), sl)
        out[name] = (*B.from_comp(layer, x0, y0), *B.from_comp(layer, x1, y1))
    return out


@tools.tool("look_background", {"required": ["layer"], "properties": {
    **ITEM, **LAYER, **FRAME, **SAMPLING,
    "tiles": {"type": "array", "items": {"type": "integer", "minimum": 1, "maximum": 26}, "minItems": 2, "maxItems": 2,
              "description": "[columns, rows] the canvas is cut into. Default: tiles about one composition frame each."},
    "tile": {"type": "string", "description": "One tile to look at close (e.g. \"B2\"), with a pixel grid. Default: the whole canvas with the tiles and the camera's frame drawn on it."},
    "grid": {"type": "integer", "minimum": 0, "description": "With `tile`: grid spacing in canvas px; 0 = none (to judge texture)."},
    "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 1400, "description": "Picture width in px."}}})
def look_background(ctx, args):
    """A big drawing (a painted background) section by section. Without `tile`: the whole canvas, cut into labelled tiles,
    with the camera's frame at the start (solid) and the end (dashed) and everything it shows over the shot (thin), so you
    see which parts are on screen and when. With `tile`: that tile alone, close, with a canvas-pixel grid (to place
    strokes) or none (grid 0, to judge texture). Use look_drawing for any other box."""
    doc = ctx.document(args.get("item"))
    layer = drawing_of(ctx, doc, args["layer"])
    frame = frame_of(ctx, layer, args.get("frame", 0))
    w, h = D.canvas_size(layer)
    comp = _comp_holding(doc, layer["id"])
    cw, ch = B.comp_size(comp) if comp else (1920.0, 1080.0)
    cols, rows = args.get("tiles") or (max(1, math.ceil(w / cw - 0.15)), max(1, math.ceil(h / ch - 0.15)))
    boxes = tile_boxes(w, h, cols, rows)
    img = canvas.rgba8(frame, w, h)
    if args.get("tile"):
        name = args["tile"].upper()
        if name not in boxes:
            raise RostrumError.not_found(ctx.tool, "tile", name, list(boxes), f"{layer['id']} cut {cols}×{rows}")
        try:
            pic = see.view(img, boxes[name], args.get("grid"), args.get("width", 1400), label=f"{layer['id']} tile {name} = x {boxes[name][0]}..{boxes[name][2]}, y {boxes[name][1]}..{boxes[name][3]}",
                           sampling=args.get("sampling", "auto"))
        except ValueError as e:
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"width" or "sampling"', str(e)) from e
        text = f"Tile {name} of {layer['id']} (canvas {w}×{h}, {cols}×{rows} tiles): x {boxes[name][0]}..{boxes[name][2]}, y {boxes[name][1]}..{boxes[name][3]}."
    else:
        pic = see.view(img, None, 0, args.get("width", 1400), sampling="smooth")
        _draw_overlay(pic, w, boxes, _frame_boxes(comp, layer) if comp else {})
        text = f"{layer['id']}: canvas {w}×{h} in {cols}×{rows} tiles ({', '.join(boxes)}); {stroke_count(frame)} strokes. Yellow = the camera's frame (solid: start, dashed: end, thin: all it shows)."
    dest = look_path(f'{doc.item_id or "doc"}_{layer["id"]}_bg{args.get("tile", "")}')
    pic.save(dest)
    return Reply(text, {"drawing": layer["id"], "canvas": [w, h], "tiles": {k: list(v) for k, v in boxes.items()}, "picture": [pic.width, pic.height]},
                 [dest], [dest], warnings=[n for n in [canvas.slow_note()] if n])


def _draw_overlay(pic, w, boxes, frames):
    k = pic.width / w
    g = ImageDraw.Draw(pic)
    for name, (x0, y0, x1, y1) in boxes.items():
        g.rectangle([x0 * k, y0 * k, x1 * k, y1 * k], outline=TILE, width=1)
        g.text((x0 * k + 6, y0 * k + 4), name, fill=TILE)
    for name, width in (("all", 1), ("start", 3), ("end", 2)):
        if name in frames:
            x0, y0, x1, y1 = (v * k for v in frames[name])
            if name == "end":
                for a in range(int(x0), int(x1), 16):
                    g.line([a, y0, min(a + 8, x1), y0], fill=CAM, width=width)
                    g.line([a, y1, min(a + 8, x1), y1], fill=CAM, width=width)
                for a in range(int(y0), int(y1), 16):
                    g.line([x0, a, x0, min(a + 8, y1)], fill=CAM, width=width)
                    g.line([x1, a, x1, min(a + 8, y1)], fill=CAM, width=width)
            else:
                g.rectangle([x0, y0, x1, y1], outline=CAM, width=width)


@tools.tool("inspect_background", {"properties": {**ITEM_COMP}})
def inspect_background(ctx, args):
    """The composition's drawing layers by depth (far first): each one's depth, how much it moves for the camera (s =
    1 / (1 + depth)), its canvas, and whether it covers everything the camera shows of it over the whole shot, in words
    (\"312 px short on the right\"). Fix a short one with background.fit."""
    _, comp = doc_and_comp(ctx, args)
    shots = B.shots(comp)
    rows = []
    for layer in comp.get("layers", []):
        if layer.get("type") != "drawing":
            continue
        gaps = [] if layer.get("screenLock") else B.gaps(comp, layer, shots)
        rows.append({"layer": layer["id"], "name": layer.get("name"), "depth": layer.get("depth", 0.0), "moves": round(1 / (1 + layer.get("depth", 0.0)), 3),
                     "canvas": [layer.get("w"), layer.get("h")], "covers": not gaps, "short": gaps,
                     "strokes": sum(stroke_count(f) for f in layer.get("frames", []))})
    rows.sort(key=lambda r: -r["depth"])
    words = "; ".join(f'{r["layer"]} ({r["name"]}) depth {r["depth"]:g}, moves ×{r["moves"]:g}, ' + ("covers the shot" if r["covers"] else ", ".join(r["short"])) for r in rows)
    return Reply(f"{comp['id']}: " + (words or "no drawing layers") + ".", {"comp": comp["id"], "layers": rows},
                 warnings=[f'{r["layer"]} is {", ".join(r["short"])}: the camera sees past it (background.fit)' for r in rows if not r["covers"]])
