"""Seeing and checking drawings: look_drawing, look_drawing_change, inspect_drawing_at, inspect_stroke_landed.

Every coordinate here is a canvas pixel (a drawing layer's own w × h; a painted element's paintW × paintH, stretched over
its box), never a composition pixel. `layer` may be a drawing or any painted element.
"""
from __future__ import annotations

import numpy as np
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_core.mcp.files import look_path
from rostrum_core.tree import index, subtree_ids
from rostrum_paint import canvas, see, where

from rostrum2d import drawing as D, paint_fields

tools = Tools()
ITEM = {"item": {"type": "string", "description": "The document's project item id. Optional when only one document is open."}}
LAYER = {"layer": {"type": "string", "description": "A drawing layer's id, or a painted element's (shape, text, image, video, path)."}}
FRAME = {"frame": {"type": "integer", "minimum": 0, "default": 0,
                   "description": "A frame number. A drawing shows its drawing with the largest `at` at or before it."}}
ZOOM = {"zoom": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4,
                 "description": "[x0, y0, x1, y1] box in canvas pixels. Default: the whole canvas."}}
GRID = {"grid": {"type": "integer", "minimum": 0, "description": "Grid spacing in canvas px (labels are canvas px). 0 = no grid. Default: chosen to fit."}}
SAMPLING = {"sampling": {"type": "string", "enum": list(see.SAMPLINGS), "default": "auto",
                         "description": "How a zoom enlarges: pixels = sharp squares, to place strokes on the grid; smooth = resampled, "
                                        "to judge texture and edges. auto = pixels with a grid, smooth with grid 0."}}


def drawing_of(ctx, doc, layer):
    """A drawing layer, or an element holding paint (paint.stroke): both are painting-kit canvases in frames."""
    painted = [i["id"] for i in doc.items() if i.get("type") == "drawing" or (i.get("type") in paint_fields.TYPES and i.get("frames"))]
    item = doc.item(layer) if doc.has(layer) else None
    if item is None:
        raise RostrumError.not_found(ctx.tool, "drawing layer", layer, painted, "this document's drawings and painted layers")
    if item["id"] not in painted:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'"{layer}"', f'is a {item.get("type")} layer with no paint',
                           painted, hint="Paint on it first (paint.stroke).")
    return item


def frame_of(ctx, drawing, n):
    """The frame item a drawing shows at frame number `n`."""
    frame = D.frame_at(drawing, n)
    if frame is None:
        firsts = [f["at"] for f in drawing.get("frames", [])]
        raise RostrumError(codes.NOT_FOUND, ctx.tool, f"frame {n} of {drawing['id']}", "shows nothing: its first drawing starts later" if firsts else "has no drawing yet",
                           hint=f"The first drawing is at frame {min(firsts)}." if firsts else "Add one with frame.add.")
    return frame


def stroke_count(frame):
    return sum(len(p.get("strokes", [])) for p in frame.get("paints", []))


def frame_holding(ctx, doc, item_id):
    """(frame item, drawing item) that hold a stroke or paint layer, found by walking up the tree."""
    cur = item_id
    while True:
        item = doc.item(cur)
        if item.get("type") == "frame":
            return item, doc.item(doc.parent_of(cur)[0])
        parent = doc.parent_of(cur)[0]
        if parent is None:
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'"{item_id}"', "is not inside a drawing frame")
        cur = parent


def blank(w, h):
    return np.zeros((h, w, 4), np.uint8)


@tools.tool("look_drawing", {"required": ["layer"], "properties": {
    **ITEM, **LAYER, **FRAME, **ZOOM, **GRID, **SAMPLING,
    "paint": {"type": "string", "description": "Show only this paint layer of the frame (its id). Default: all paint layers together."},
    "onion": {"anyOf": [{"type": "boolean"}, {"type": "object", "additionalProperties": False, "properties": {
        "before": {"type": "integer", "minimum": 0, "maximum": 5}, "after": {"type": "integer", "minimum": 0, "maximum": 5}}}],
        "default": False, "description": "Also show the drawings before (red) and after (green), faint, under this one: "
                                         "true = 2 each way, or {before, after} = so many each way (0 – 5), as the screen's onion skin."},
    "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 1200, "description": "Picture width in px."}}})
def look_drawing(ctx, args):
    """One drawing of a drawing layer, in canvas pixels: the frame shown at a frame number, optionally zoomed, with a labelled
    pixel grid, one paint layer alone, or onion skin. Transparent paper shows as a checkerboard."""
    doc = ctx.document(args.get("item"))
    drawing = drawing_of(ctx, doc, args["layer"])
    n = args.get("frame", 0)
    frame = frame_of(ctx, drawing, n)
    w, h = D.canvas_size(drawing)
    paint = args.get("paint")
    if paint is not None and paint not in [p["id"] for p in frame.get("paints", [])]:
        raise RostrumError.not_found(ctx.tool, "paint layer", paint, [p["id"] for p in frame.get("paints", [])], f"frame {frame['id']}")
    img = canvas.layer_rgba(frame, paint, w, h) if paint else canvas.rgba8(frame, w, h)
    onion = args.get("onion")
    if onion:
        reach = onion if isinstance(onion, dict) else {}
        b, a = reach.get("before", 2), reach.get("after", 2)
        before, after = D.neighbours(drawing, frame["id"], max(a, b))
        before, after = before[:b], after[:a]
        img = see.onion(img, [canvas.rgba8(f, w, h) for f in before], [canvas.rgba8(f, w, h) for f in after])
    note = f'{drawing["id"]} frame {n} (drawing {frame["id"]} at {frame["at"]})' + (f", paint {paint}" if paint else "") + (", onion skin" if args.get("onion") else "")
    try:
        pic = see.view(img, args.get("zoom"), args.get("grid"), args.get("width", 1200), label=note, sampling=args.get("sampling", "auto"))
    except ValueError as e:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"zoom", "width" or "sampling"', str(e)) from e
    dest = look_path(f'{doc.item_id or "doc"}_{drawing["id"]}_f{n}')
    pic.save(dest)
    return Reply(f'{drawing["id"]} at frame {n} shows drawing {frame["id"]} (at {frame["at"]}): {stroke_count(frame)} strokes on {len(frame.get("paints", []))} paint layer(s), canvas {w}×{h}.',
                 {"drawing": drawing["id"], "frame_item": frame["id"], "at": frame["at"], "strokes": stroke_count(frame), "canvas": [w, h],
                  "zoom": args.get("zoom"), "picture": [pic.width, pic.height], "stamper": canvas.STAMPER}, [dest], [dest],
                 warnings=[n for n in [canvas.slow_note()] if n])


def last_change_touching(doc, frame):
    """The latest change with an edit inside the frame (the frame itself, its paint layers, strokes, masks), or None."""
    inside = set(subtree_ids(frame, doc.kind.lists))
    for c in reversed(doc.history.changes):
        for e in c.edits:
            if e.id in inside or getattr(e, "parent", None) in inside:
                return c
    return None


@tools.tool("look_drawing_change", {"required": ["layer"], "properties": {**ITEM, **LAYER, **FRAME, **ZOOM, **GRID, **SAMPLING}})
def look_drawing_change(ctx, args):
    """Before | after | difference of the last change that touched one drawing of a layer (a stroke, an undo, a clear …),
    with the changed box outlined and its canvas-pixel coordinates written."""
    doc = ctx.document(args.get("item"))
    drawing = drawing_of(ctx, doc, args["layer"])
    n = args.get("frame", 0)
    frame = frame_of(ctx, drawing, n)
    w, h = D.canvas_size(drawing)
    c = last_change_touching(doc, frame)
    if c is None:
        raise RostrumError(codes.NOT_FOUND, ctx.tool, f"change to drawing {frame['id']}", "no change in the history touched it", hint="Draw something first (stroke.add).")
    old = index(doc.at_step(c.seq - 1), doc.kind.lists).get(frame["id"])
    before = canvas.rgba8(old.item, w, h) if old else blank(w, h)
    try:
        pic = see.before_after(before, canvas.rgba8(frame, w, h), args.get("zoom"), args.get("grid"), sampling=args.get("sampling", "auto"))
    except ValueError as e:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"zoom"', str(e)) from e
    box = see.changed_box(before, canvas.rgba8(frame, w, h))
    dest = look_path(f'{doc.item_id or "doc"}_{drawing["id"]}_change{c.seq}')
    pic.save(dest)
    what = f'change {c.seq} by {c.who}, "{c.label}"'
    return Reply(f'Drawing {frame["id"]} (frame {n}) before and after {what}: ' + (f"changed box x {box[0]}..{box[2]}, y {box[1]}..{box[3]}." if box else "no pixel changed."),
                 {"frame_item": frame["id"], "seq": c.seq, "who": str(c.who), "label": c.label, "changed_box": list(box) if box else None}, [dest], [dest])


def top_stroke(r):
    return r.get("stroke")


@tools.tool("inspect_drawing_at", {"required": ["layer", "x", "y"], "properties": {
    **ITEM, **LAYER, **FRAME, "x": {"type": "integer", "description": "Canvas pixels from the left."}, "y": {"type": "integer", "description": "Canvas pixels from the top."}}})
def inspect_drawing_at(ctx, args):
    """What is at a canvas pixel of one drawing: its colour, each paint layer's colour there, the top stroke (and who drew it), masks."""
    doc = ctx.document(args.get("item"))
    drawing = drawing_of(ctx, doc, args["layer"])
    frame = frame_of(ctx, drawing, args.get("frame", 0))
    w, h = D.canvas_size(drawing)
    x, y = args["x"], args["y"]
    if not (0 <= x < w and 0 <= y < h):
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"point ({x}, {y})", f"is outside the {w}×{h} canvas", hint=f"x is 0..{w - 1}, y is 0..{h - 1}.")
    r = where.what(frame, w, h, x, y)
    sid, by = top_stroke(r), None
    if sid:
        c = doc.who_changed(sid)
        by = {"who": str(c.who), "label": c.label, "seq": c.seq} if c else None
    r = {**r, "frame_item": frame["id"], "drawn_by": by}
    text = f"Drawing {frame['id']} at ({x}, {y}): " + (f'top stroke {sid}' + (f', drawn by {by["who"]} ("{by["label"]}")' if by else "") if sid else "no stroke paints here") + "."
    return Reply(text, r)


@tools.tool("inspect_stroke_landed", {"required": ["stroke"], "properties": {
    **ITEM, "stroke": {"type": "string", "description": "A stroke's id."},
    "path": {"type": "array", "items": {"type": "array", "items": {"type": "number"}, "minItems": 2},
             "description": "[[x, y], …] the path you meant, in canvas pixels. Default: the stroke's own points."}}})
def inspect_stroke_landed(ctx, args):
    """Did a stroke land where it was meant to: whether it left paint, how far the paint is from the path (mean / max px) and how much of it
    sits on the path. Answers in words."""
    doc = ctx.document(args.get("item"))
    sid = args["stroke"]
    if not doc.has(sid) or doc.item(sid).get("type") != "stroke":
        raise RostrumError.not_found(ctx.tool, "stroke", sid, [i["id"] for i in doc.items() if i.get("type") == "stroke"][:12], "this document")
    frame, drawing = frame_holding(ctx, doc, sid)
    w, h = D.canvas_size(drawing)
    r = where.landed(frame, w, h, sid, args.get("path"))
    return Reply(where.landed_text(r), {**r, "frame_item": frame["id"], "canvas": [w, h]})
