"""look_frame and look_frame (what: sheet): the agent's eyes on the picture, drawn by the same engine as export (preview ≡ export)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools, sheet
from rostrum_core.mcp.files import look_path

from . import render
from .geometry import comp_size, flatten, problems_showing
from .pick import ITEM_COMP, TIME, doc_and_comp, time_of

tools = Tools()
FRAME_WIDTH = 960
SHEET_WIDTH = 1600      # the whole contact sheet (tiles, gaps and margins): 4 across makes ~390 px tiles, big enough to judge


def shown_ids(comp: dict, t: float) -> list[str]:
    w, h = comp_size(comp)
    return [n["id"] for n in flatten(comp, t) if n["type"] != "group" and not problems_showing(n, w, h)]


TIMES = {"times": {"type": "array", "items": {"type": "number", "minimum": 0}, "minItems": 1, "maxItems": 24,
                   "description": "Seconds, several: one contact sheet of exactly these moments (instead of time / frame), e.g. [0.5, 1.2, 3.0]. Each tile is labelled with its time. (what \"sheet\" is the same picture for `count` moments spread evenly from start to end.)"}}


@tools.tool("look_frame", {"properties": {**ITEM_COMP, **TIME, **TIMES, "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": FRAME_WIDTH,
                                                                          "description": "Picture width in px (never larger than the composition). Default 960; with `times`, the width of the whole sheet, which its tiles share (default 1600: ~390 px tiles 4 across; fewer times give bigger tiles)."}}})
def look_frame(ctx, args):
    """One rendered frame of a composition at a time (seconds) or frame number, as a PNG file and as an image you can see.
    Give `times: [0.5, 1.2, 3.0]` for one contact sheet of exactly those moments in one call; what "sheet" makes the same
    sheet from `start`, `end`, `count` (evenly spaced). A sheet is for the whole motion at a glance; for detail look at
    one frame (960 px, or `width` up to the comp's), or a sheet of 2-4 moments.
    Also lists which layers are on screen then (approximate: judged from their values, not from pixels). A frame the engine
    can't finish (stuck about 2 minutes) fails with an error naming it, never a silent wait."""
    doc, comp = doc_and_comp(ctx, args)
    if "times" in args:
        return _times_sheet(ctx, doc, comp, args)
    t, frame = time_of(ctx, comp, args)
    scene, width = render.scene_of(doc, comp["id"], (t, t)), args.get("width", FRAME_WIDTH)
    dest = look_path(f'{doc.item_id or "doc"}_{comp["id"]}_f{frame}', project=doc.folder)
    seen = shown_ids(comp, t)

    def job_fn(job):
        with tempfile.TemporaryDirectory(prefix="rostrum_look_") as tmp:
            raw = Path(tmp) / "raw.png"
            render.stills(ctx.tool, scene, [(t, raw)])
            w, h = sheet.scaled_copy(raw, width, dest)
        return Reply(f'Frame {frame} ({t:.3f} s) of {comp["id"]}, {w}×{h}. On screen: {", ".join(seen) or "nothing"}.',
                     {"time": t, "frame": frame, "width": w, "height": h, "on_screen": seen}, [dest], [dest],
                     scene.get("warnings", []))

    return ctx.long(f'look_frame {comp["id"]} f{frame}', job_fn)


def _times_sheet(ctx, doc, comp, args: dict):
    """look_frame `times`: a contact sheet of those moments; a bad list is refused whole, naming the moment."""
    for other in ("time", "frame"):
        if other in args:
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'"times" and "{other}"', "were both given", ["times", other], "Give one: times for a sheet, time or frame for one picture.")
    fps, frames_in_comp = comp.get("fps", 30), round(comp.get("duration", 5.0) * comp.get("fps", 30))
    frames = []
    for t in args["times"]:
        f = round(t * fps)
        if not 0 <= f < frames_in_comp:
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"time {t} s", f"is outside the composition (0 to {(frames_in_comp - 1) / fps:.3f} s, its last frame)")
        frames.append(f)
    return _sheet_of(ctx, doc, comp, sorted(set(frames)), args)


@tools.tool("look_sheet", {"properties": {**ITEM_COMP, "start": {"type": "number", "minimum": 0, "description": "Seconds. Default 0."},
                                           "end": {"type": "number", "minimum": 0, "description": "Seconds. Default (and the comp's duration): the last frame."},
                                           "count": {"type": "integer", "minimum": 2, "maximum": 24, "default": 8, "description": "Frames in the sheet, evenly spaced from start to end."},
                                           "cols": {"type": "integer", "minimum": 1, "maximum": 8, "description": "Tiles per row. Default 4 (fewer when count is small)."},
                                           "width": {"type": "integer", "minimum": 256, "maximum": 2048, "default": SHEET_WIDTH,
                                                     "description": "Width of the whole sheet in px (default 1600: ~390 px tiles 4 across); the tiles share it."}}})
def look_sheet(ctx, args):
    """A contact sheet: `count` frames spread over a time range (`start`, `end` in seconds) in one image `width` px wide,
    each tile labelled with its time and frame, e.g. {"what": "sheet", "start": 2, "end": 5, "count": 12}. Use it to check
    a whole motion at a glance; look_frame for detail. Tiles are drawn at their own size, so a big sheet stays quick.
    For moments you choose (not evenly spaced) give look_frame `times` instead: the same sheet."""
    doc, comp = doc_and_comp(ctx, args)
    fps, duration = comp.get("fps", 30), comp.get("duration", 5.0)
    last = (round(duration * fps) - 1) / fps
    start, end, count = args.get("start", 0.0), args.get("end", last), args.get("count", 8)
    end = last if last < end <= duration + 1e-9 else end        # the comp's end time is its last frame
    if not 0 <= start < end <= last + 1e-9:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'range {start}–{end} s', f"must satisfy 0 <= start < end <= {last:.3f} (the last frame)")
    frames = sorted({round((start + (end - start) * i / (count - 1)) * fps) for i in range(count)})
    return _sheet_of(ctx, doc, comp, frames, args)


def _sheet_of(ctx, doc, comp, frames: list[int], args: dict):
    """The one contact-sheet path: the frames (whole numbers, sorted) of a composition as one labelled picture."""
    fps = comp.get("fps", 30)
    scene = render.scene_of(doc, comp["id"], (frames[0] / fps, frames[-1] / fps), frames)
    cols = min(args.get("cols", 4), len(frames))
    tile_w = sheet.tile_width(args.get("width", SHEET_WIDTH), cols)
    dest = look_path(f'{doc.item_id or "doc"}_{comp["id"]}_sheet', project=doc.folder)

    def job_fn(job):
        with tempfile.TemporaryDirectory(prefix="rostrum_sheet_") as tmp:
            items = [(f / fps, Path(tmp) / f"f{f}.png") for f in frames]
            render.small_stills(ctx.tool, scene, items, tile_w, job.progress)
            tiles = [(png, f"{t:.2f} s   f{f}") for (t, png), f in zip(items, frames)]
            w, h = sheet.contact_sheet(tiles, tile_w, cols, dest)
        return Reply(f'Contact sheet of {comp["id"]}: {len(frames)} frames from {frames[0] / fps:.2f} to {frames[-1] / fps:.2f} s, {w}×{h}.',
                     {"frames": frames, "times": [round(f / fps, 4) for f in frames], "width": w, "height": h, "cols": cols}, [dest], [dest],
                     scene.get("warnings", []))

    return ctx.long(f'look_frame (what: sheet) {comp["id"]}', job_fn)
