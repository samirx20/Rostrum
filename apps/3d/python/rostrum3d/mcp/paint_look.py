"""The agent's paint tools: look_paint (the canvas itself), inspect_paint_strokes (where each stroke landed and how far off),
look_coverage (what the shot sees painted), look_where (a canvas spot → the shot's picture and the world).

Every canvas coordinate is a canvas pixel of the item's square paint picture (paintSize; x right, y down) or a uv
(x = u × paintSize, y = (1 − v) × paintSize); guide `painting`. The canvas is the one the renderer lays
(paint_canvas.laid), and the shot's view of it comes from the engine's texel picture (texels.py).
"""
from __future__ import annotations

import numpy as np
from PIL import Image
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_core.mcp.files import look_path
from rostrum_paint import see, where

from rostrum3d import paint_view
from rostrum3d.paint_fields import CHANNELS

from . import draw, paint_canvas as PC, paint_spots as PS
from .shot import ITEM_SHOT, TIME, doc_and_shot, frame_of, seconds, size_of

tools = Tools()
TARGET = {"target": {"type": "string", "description": "The mesh's or clay's id."}}
PIC = {"width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 960, "description": "Width of the shot's picture in px (the height follows the shot). Default 960."}}
ZOOM = {"zoom": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4, "description": "[x0, y0, x1, y1] box in canvas px. Default: the whole canvas."},
        "grid": {"type": "integer", "minimum": 0, "description": "Grid spacing in canvas px, labelled. 0 = no grid. Default: chosen to fit."},
        "sampling": {"enum": list(see.SAMPLINGS), "default": "auto", "description": "How a zoom enlarges: pixels (sharp squares, to place strokes), "
                                                                                     "smooth (to judge edges); auto = pixels with a grid."}}


def _texels(ctx, doc, info, frame, w, h, scene):
    """The shot camera's texel picture (the shared cache the screen's coverage uses, else the engine)."""
    return PC.texels_for(ctx, scene)({"camera": info["camera"], "frame": frame, "width": w, "height": h})


def _bad(ctx, what, e):
    raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, what, str(e)) from e


@tools.tool("look_paint", {"required": ["target"], "properties": {
    **ITEM_SHOT, **TARGET, **ZOOM,
    "layer": {"type": "string", "description": "Show only this paint layer (its id)."},
    "channel": {"enum": list(CHANNELS), "description": "Show only the layers painting this channel (colour, roughness, height = Relief, metal, glow)."},
    "size": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 1200, "description": "Picture width in px."}}})
def look_paint(ctx, args):
    """A mesh's or clay's paint canvas as a picture: the flat paint picture (paintSize square) the renderer lays on its
    unfolded surface, every layer together, one `layer` or one `channel`; transparent (unpainted) shows as a checkerboard.
    `zoom` a box and `grid` labels canvas pixels, the coordinates of stroke.add's `points`. A clay's anchored strokes and
    strokes From the view are shown laid, as the render gets them. Where a canvas spot is on the shot: look_where."""
    doc, info = doc_and_shot(ctx, args)
    item = PC.paintable(ctx, doc, args["target"])
    if args.get("layer") and args["layer"] not in [p["id"] for p in item.get("paints", [])]:
        raise RostrumError.not_found(ctx.tool, "paint layer", args["layer"], [p["id"] for p in item.get("paints", [])], f'{item["id"]}\'s layers')
    size = PC.size_of(item)
    scene = draw.scene_of(doc, info["id"]) if item["type"] == "clay" or PC.has_view(item) else None

    def job_fn(job):
        held = PC.laid(ctx, scene, item, doc.folder)
        px = PC.picture(held, size, args.get("layer"), args.get("channel"))
        what = f'layer {args["layer"]}' if args.get("layer") else f'{CHANNELS[args["channel"]][0]} layers' if args.get("channel") else "all layers"
        try:
            pic = see.view(px, args.get("zoom"), args.get("grid"), args.get("size", 1200), label=f'{item["id"]} - {what} - {size} x {size} canvas px',
                           sampling=args.get("sampling", "auto"))
        except ValueError as e:
            _bad(ctx, '"zoom", "size" or "sampling"', e)
        dest = look_path(f'{doc.item_id or "doc"}_{item["id"]}_paint', project=doc.folder)
        pic.save(dest)
        layers = [{"id": p["id"], "name": p.get("name"), "channel": p.get("channel", "colour"), "visible": p.get("visible", True),
                   "strokes": len(p.get("strokes", []))} for p in item.get("paints", [])]
        box = see.changed_box(np.zeros_like(px), px)
        said = (f'{item["id"]}: {what}, canvas {size}×{size} px, {len(layers)} layer(s) '
                + ("(" + ", ".join(f'{l["id"]}: {CHANNELS[l["channel"]][0]}, {l["strokes"]} stroke(s)' for l in layers) + ")" if layers else "(none yet: paint.add)")
                + (f'; paint within x {box[0]}–{box[2]}, y {box[1]}–{box[3]}' if box else "; nothing painted") + ".")
        return Reply(said, {"item": item["id"], "canvas": [size, size], "layers": layers, "paintedBox": list(box) if box else None,
                            "picture": [pic.width, pic.height]}, [dest], [dest])

    return ctx.long(f'look_paint {item["id"]}', job_fn)


def _rows_surface(held: dict, size: int, item: dict, layer: dict) -> list[dict]:
    """One row per own stroke of `layer` (a clay's anchored stroke: its laid pieces together)."""
    laid_strokes = next(p for p in held["paints"] if p["id"] == layer["id"])["strokes"]
    rows = []
    for s in layer.get("strokes", []):
        if s.get("type") == "fill" or paint_view.view_of(s):
            continue
        pieces = [q for q in laid_strokes if q["id"] == s["id"] or q["id"].startswith(s["id"] + ".")]
        got = [where.landed(held, size, size, q["id"]) for q in pieces]
        boxes = [PS.box(q.get("points"), float(q.get("size", 0)), size) for q in pieces]
        boxes = [b for b in boxes if b]
        box = [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)] if boxes else None
        worst = next((g for g in got if not g["landed"]), None)
        means = [g["mean"] for g in got if g.get("mean") is not None]
        rows.append({"stroke": s["id"], "layer": layer["id"], "items": [item["id"]], "anchored": bool(s.get("anchors")), "pieces": len(pieces),
                     "landed": bool(got) and worst is None, "offPx": round(max(means), 2) if means else None,
                     "verdict": worst["verdict"] if worst else "landed" if got else "laid no paint", "box": box, "uvBox": PS.uv_box(box, size)})
    return rows


def _rows_view(ctx, doc, scene, item, layer) -> list[dict]:
    """One row per stroke From the view of `layer`, measured through its own camera (paint_view.landed_on)."""
    views = {s["id"]: v for s in layer.get("strokes", []) if (v := paint_view.view_of(s))}
    if not views:
        return []
    found = paint_view.landed_on({**item, "paints": [layer]}, PC.texels_for(ctx, PC.loaded(ctx, scene)))
    rows = []
    for r in found:
        v = views[r["stroke"]]
        holders = [i["id"] for i in doc.items() if i.get("type") in PC.PAINTABLE
                   and any(paint_view.view_of(s) == v for p in i.get("paints", []) for s in p.get("strokes", []))]
        box = PS.box([q for run in r["canvasPx"] for q in run], 0, PC.size_of(item))
        rows.append({"stroke": r["stroke"], "layer": layer["id"], "view": True, "items": holders, "runs": r["runs"], "share": r["share"],
                     "landed": r["runs"] > 0, "offPx": r["offPx"]["mean"], "offMaxPx": r["offPx"]["max"], "box": box,
                     "uvBox": PS.uv_box(box, PC.size_of(item)),
                     "verdict": "landed" if r["runs"] else f'laid no paint: {item["id"]} is not under its path from that view'})
    return rows


@tools.tool("inspect_paint_strokes", {"required": ["target"], "properties": {
    **ITEM_SHOT, "target": {"type": "string", "description": "A mesh's or clay's id (every layer), or one paint layer's id."}}})
def inspect_paint_strokes(ctx, args):
    """Where each stroke of a mesh or clay (or of one paint layer) landed and how far off, one plain line each:
    "stroke s3 (From the view, layer paint_1): landed on case and lid, 1.2 screen px off". A stroke on the surface
    (canvas `points`, or a clay's `anchors` laid as the render lays them) is measured on the canvas: how far its paint's
    centre sits from its path, in canvas px (landed = within a tenth of the brush, at least 2 px). A stroke From the view is
    measured through its own camera: how far the paint lands from the path you drew, in screen px of that view, and which
    items it landed on. Each row has the canvas px box and uv box it covers."""
    doc, info = doc_and_shot(ctx, args)
    tid = args["target"]
    owner = next((i for i in doc.items() if i.get("type") in PC.PAINTABLE and any(p["id"] == tid for p in i.get("paints", []))), None)
    item = owner or PC.paintable(ctx, doc, tid)
    layers = [p for p in item.get("paints", []) if owner is None or p["id"] == tid]
    scene = draw.scene_of(doc, info["id"]) if item["type"] == "clay" or PC.has_view(item) else None

    def job_fn(job):
        held = PC.laid(ctx, scene, item, doc.folder)
        size = PC.size_of(item)
        rows = []
        for layer in layers:
            rows += _rows_surface(held, size, item, layer) + _rows_view(ctx, doc, scene, item, layer)
        text = "\n".join(PS.stroke_line(r) for r in rows) or f'{tid} has no strokes yet.'
        return Reply(text, {"item": item["id"], "canvas": [size, size], "strokes": rows})

    return ctx.long(f'inspect_paint_strokes {tid}', job_fn)


@tools.tool("look_coverage", {"properties": {**ITEM_SHOT, **TIME, **PIC}})
def look_coverage(ctx, args):
    """How much of each paintable mesh and clay the shot's camera sees is painted, at a frame: "lid: 62 % painted
    (41 000 of 66 000 px seen)", a spot counting as painted where any shown layer's paint is at least half opaque (as the screen's count), and a picture of the frame with what is seen but unpainted hatched
    orange (the screen's coverage tint). Paint where the hatch is: look_at there gives the uv. An item seen without
    surface coordinates (a mesh never unfolded) can't be painted until mesh.unfold."""
    doc, info = doc_and_shot(ctx, args)
    frame = frame_of(ctx, info, args)
    w, h = size_of(info, args)
    scene, engine = draw.scene_of(doc, info["id"]), draw.engine_of(ctx)
    dest = look_path(f'{doc.item_id or "doc"}_{info["id"]}_f{frame}_coverage', project=doc.folder)

    def job_fn(job):
        from rostrum3d import coverage
        pic = _texels(ctx, doc, info, frame, w, h, scene)
        canvases, alphas = {}, {}
        for idx, iid in enumerate(pic.items):
            if doc.has(iid) and doc.item(iid).get("type") in PC.PAINTABLE and pic.of(iid).any():
                it = doc.item(iid)
                alphas[idx] = PC.alpha(PC.laid(ctx, scene, it, doc.folder), PC.size_of(it))
                canvases[iid] = alphas[idx]
        got = coverage.measure(pic, canvases)
        draw.render(ctx.tool, f"frame {frame} of {info['id']}", engine, scene, camera=info["camera"], renderer="storm",
                    frame=frame, width=w, height=h, png=str(dest))
        seen, painted = PS.painted_on_screen(pic.uv, pic.item, alphas)
        with Image.open(dest) as im:
            rgb = np.asarray(im.convert("RGB"))
        Image.fromarray(PS.hatch(rgb, seen & ~painted)).save(dest)
        no_uv = [iid for idx, iid in enumerate(pic.items) if idx in alphas and not np.isfinite(pic.uv[pic.of(iid)]).any()]
        lines = [f'{iid}: {r["percent"]:.0f} % painted ({r["painted"]} of {r["seen"]} px seen)' for iid, r in got.items() if iid not in no_uv]
        lines += [f'{iid}: seen, but has no unfolded surface (mesh.unfold first)' for iid in no_uv]
        t = seconds(info, frame)
        return Reply(f'Seen by {info["id"]} at frame {frame} ({t:.3f} s), {w}×{h}: ' + ("; ".join(lines) if lines else "no paintable mesh or clay in view")
                     + ". Hatched orange: seen, not painted.", {"frame": frame, "time": t, "width": w, "height": h, "camera": info["camera"],
                                                                "items": got, "noSurface": no_uv}, [dest], [dest], engine.take_notices())

    return ctx.long(f'look_coverage {info["id"]} f{frame}', job_fn)


@tools.tool("look_where", {"required": ["target"], "properties": {
    **ITEM_SHOT, **TIME, **TARGET, **PIC,
    "px": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2, "description": "[x, y] canvas px of the item's paint picture."},
    "uv": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2, "description": "[u, v] on the item's unfolded surface (instead of px)."}}})
def look_where(ctx, args):
    """The reverse of look_at: where a spot of a mesh's or clay's paint canvas (`px` canvas pixels, or `uv`) is on the
    shot's picture at a frame and in the world. Seen: its pixel in a `width` picture, the world point (metres), the
    distance and the surface direction there. Not seen (behind something, facing away or out of frame): says so, with the
    nearest pixel where the item is seen and how far that is on the canvas."""
    doc, info = doc_and_shot(ctx, args)
    item = PC.paintable(ctx, doc, args["target"])
    size = PC.size_of(item)
    if ("px" in args) == ("uv" in args):
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"px" and "uv"', "need exactly one of them", ["px", "uv"])
    uv = args["uv"] if "uv" in args else PS.uv_of(args["px"], size)
    px = PS.px_of(uv, size)
    frame = frame_of(ctx, info, args)
    w, h = size_of(info, args)
    scene, engine = draw.scene_of(doc, info["id"]), draw.engine_of(ctx)

    def job_fn(job):
        pic = _texels(ctx, doc, info, frame, w, h, scene)
        spot = f'{item["id"]} canvas ({px[0]:.0f}, {px[1]:.0f}) = uv ({uv[0]:.4f}, {uv[1]:.4f})'
        r = PS.nearest_seen(pic.uv, pic.of(item["id"]), uv, size) if item["id"] in pic.items else None
        data = {"item": item["id"], "canvasPx": [round(c, 2) for c in px], "uv": [round(c, 5) for c in uv], "frame": frame, "width": w, "height": h}
        if r is None:
            return Reply(f'{spot}: {item["id"]} is not in {info["id"]}\'s picture at frame {frame}.', {**data, "seen": False})
        if not r["seen"]:
            return Reply(f'{spot}: not seen from {info["id"]} (behind something, facing away or out of frame); the nearest seen spot of '
                         f'{item["id"]} is pixel ({r["pixel"][0]}, {r["pixel"][1]}), {r["offPx"]:.0f} canvas px away.', {**data, **r})
        x, y = r["pixel"]
        hit = draw.call(ctx.tool, f"point ({x}, {y})", engine, scene, "pick", camera=info["camera"], frame=frame, width=w, height=h, x=x, y=y)
        world = {k: hit[k] for k in ("point", "normal", "distance") if k in hit}
        return Reply(f'{spot}: seen by {info["id"]} at pixel ({x}, {y}) of {w}×{h}'
                     + (f', world {[round(c, 3) for c in hit["point"]]}, {hit["distance"]:.3g} m away, facing {[round(c, 2) for c in hit["normal"]]}'
                        if hit.get("hit") and hit.get("item") == item["id"] else "") + ".", {**data, **r, **world})

    return ctx.long(f'look_where {item["id"]}', job_fn)
