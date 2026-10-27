"""How much of a drawing is painted and where bare paper shows: look_drawing (what: coverage), paint_coverage.py's report
as a tool. Canvas px, as every drawing tool; each gap also in composition px when the drawing sits straight in it."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_core.mcp.files import look_path

from rostrum2d import drawing as D, exprbake, paint_coverage as C, write_on

from .draw import ITEM, LAYER, drawing_of, frame_of

tools = Tools()


@tools.tool("look_coverage", {"required": ["layer"], "properties": {
    **ITEM, **LAYER,
    "time": {"type": "number", "minimum": 0, "description": "Seconds: the drawing shown then, as far as drawnSoFar has painted "
                                                             "it then. Default 0 (or give frame). A painting: its first drawing, all drawn."},
    "frame": {"type": "integer", "minimum": 0, "description": "A frame number instead of time."},
    "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": 1200, "description": "Picture width in px."}}})
def look_coverage(ctx, args):
    """How much of a drawing's canvas is painted at a time, per paint layer and together, and where bare paper shows: each
    gap as a canvas px box in words ("bare paper: a 1920×90 px strip along the bottom edge, the full width, x 0–1920,
    y 990–1080"). Painted = paint at least 60 % opaque; thin = 15–60 % (a pale glaze); bare = less. The picture tints bare
    paper magenta and boxes each gap (1 = the biggest). A drawing placed straight in the composition is measured over the
    part of its canvas the composition shows (the frame at rest), else the whole canvas. Run it between painting passes, and at times while drawnSoFar paints on."""
    doc = ctx.document(args.get("item"))
    drawing = drawing_of(ctx, doc, args["layer"])
    try:
        comp = exprbake.comp_of(doc.data, drawing["id"])
    except StopIteration:
        comp = None
    fps = comp.get("fps", 30) if comp else 30
    if "time" in args and "frame" in args:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"time" and "frame"', "were both given", ["time", "frame"], "Give one.")
    t = args["frame"] / fps if "frame" in args else float(args.get("time", 0.0))
    n = D.frame_number(t, fps)
    frame = frame_of(ctx, drawing, n)
    w, h = D.canvas_size(drawing)
    amount = write_on.amount_at(drawing, t) if comp else 1.0
    window = C.comp_window(drawing, comp, w, h, t) if comp else None
    rep, rgba, bare = C.report(frame, w, h, amount, window, (comp["width"], comp["height"]) if window else None)
    pic = C.picture(rgba, bare, rep["gaps"], window)
    width = int(args.get("width", 1200))
    if pic.width > width:
        pic = pic.resize((width, max(1, round(pic.height * width / pic.width))))
    dest = look_path(f'{doc.item_id or "doc"}_{drawing["id"]}_coverage_{n}', project=doc.folder)
    pic.save(dest)
    pct = lambda x: f"{round(100 * x)} %"  # noqa: E731
    layers = "; ".join(f'{p["paint"]} ({p["name"]}) {pct(p["painted"])} painted, {pct(p["thin"])} thin'
                       + (f', {pct(p["drawn"])} drawn' if p["drawn"] < 1 else "") + (" (hidden)" if p.get("hidden") else "")
                       for p in rep["layers"])
    gaps = " ".join(f'{i}. {g["words"]}.' for i, g in enumerate(rep["gaps"], 1)) or "No bare area worth naming."
    where = f", over the part the composition shows (canvas px {window})" if window else ", the whole canvas"
    return Reply(f'{drawing["id"]} at {round(t, 3)} s (frame {n}, {pct(amount)} drawn so far), canvas {w}×{h}{where}: '
                 f'{pct(rep["painted"])} painted, '
                 f'{pct(rep["thin"])} thin, {pct(rep["bare"])} bare paper. Paint layers: {layers}. {gaps}',
                 {"drawing": drawing["id"], "time": t, "frame": n, "drawnSoFar": amount, "canvas": [w, h], "window": window, **rep}, [dest], [dest])
