"""look_frame and look_frame (what: sheet): the agent's eyes on the picture, drawn by the same engine as export (preview ≡ export)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools, sheet
from rostrum_core.mcp.files import look_path

from . import render, video_frames
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


AREA = {"area": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4,
                 "description": "[x, y, w, h] in comp px: only that part, drawn sharp at `width` (a zoom on a mouth, a "
                                "hand, an edge; e.g. [860, 380, 200, 120]). One frame only (not with `times`)."},
        "cols": {"type": "integer", "minimum": 1, "maximum": 8, "description": "With `times`: tiles per row. Default 4 "
                                                                                "(fewer when there are fewer times)."}}


@tools.tool("look_frame", {"properties": {**ITEM_COMP, **TIME, **TIMES, **AREA, **video_frames.VIDEO, "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": FRAME_WIDTH,
                                                                          "description": "Picture width in px (never larger than the composition; with `area`, any up to 4096: the zoom). Default 960; with `times`, the width of the whole sheet, which its tiles share (default 1600: ~390 px tiles 4 across; fewer times give bigger tiles)."}}})
def look_frame(ctx, args):
    """One rendered frame of a composition at a time (seconds) or frame number, as a PNG file and as an image you can see.
    Give `times: [0.5, 1.2, 3.0]` for one contact sheet of exactly those moments in one call; what "sheet" makes the same
    sheet from `start`, `end`, `count` (evenly spaced). A sheet is for the whole motion at a glance; for detail look at
    one frame (960 px, or `width` up to the comp's), a sheet of 2-4 moments, or `area` [x, y, w, h] (comp px): only that
    part, drawn sharp at `width` (a zoom: a mouth, a hand, an edge).
    Also lists which layers are on screen then (approximate: judged from their values, not from pixels). A frame the engine
    can't finish (stuck about 2 minutes) fails with an error naming it, never a silent wait.
    `video`: the path of a finished mp4 (render_video's `video`) with `times` (or one `time`): the sheet is made of the film's
    own frames, so you look at the export itself."""
    if "video" in args:
        if "area" in args or "frame" in args:
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"video" with "area" or "frame"', "is not supported", ["times", "time"], "A film is looked at by seconds: times [..] (or one time).")
        return video_frames.video_sheet(ctx, args, args["times"] if "times" in args else [args.get("time", 0.0)])
    doc, comp = doc_and_comp(ctx, args)
    if "times" in args:
        if "area" in args:
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"area" and "times"', "were both given", ["area", "times"],
                               "A zoom is one frame: give time (or frame) with area.")
        return _times_sheet(ctx, doc, comp, args)
    if "cols" in args:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"cols"', "is for a sheet", ["times"], "Give cols with times.")
    t, frame = time_of(ctx, comp, args)
    if "area" in args:
        return _area(ctx, doc, comp, t, frame, args)
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


def _area(ctx, doc, comp, t, frame, args):
    x, y, w, h = args["area"]
    cw, ch = comp_size(comp)
    if w <= 0 or h <= 0 or x >= cw or y >= ch or x + w <= 0 or y + h <= 0:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'area {args["area"]}', f"has no area inside the composition (0, 0, {cw:g}, {ch:g})",
                           hint="[x, y, w, h] in comp px, w and h above 0.")
    width = min(args.get("width", FRAME_WIDTH), 4096)
    scene = render.scene_of(doc, comp["id"], (t, t))
    dest = look_path(f'{doc.item_id or "doc"}_{comp["id"]}_f{frame}_area', project=doc.folder)

    def job_fn(job):
        pw, ph = render.area_still(ctx.tool, scene, t, (x, y, w, h), width, dest)
        return Reply(f'Frame {frame} ({t:.3f} s) of {comp["id"]}, area [{x:g}, {y:g}, {w:g}, {h:g}] (comp px) drawn {pw}×{ph} '
                     f'({pw / w:.2g}× zoom).', {"time": t, "frame": frame, "area": [x, y, w, h], "width": pw, "height": ph,
                                               "zoom": round(pw / w, 3)}, [dest], [dest], scene.get("warnings", []))

    return ctx.long(f'look_frame {comp["id"]} f{frame} area', job_fn)


def _times_sheet(ctx, doc, comp, args: dict):
    """look_frame `times`: a contact sheet of those moments; a bad list is refused whole, naming the moment."""
    for other in ("time", "frame"):
        if other in args:
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'"times" and "{other}"', "were both given", ["times", other], "Give one: times for a sheet, time or frame for one picture.")
    fps, frames_in_comp = comp.get("fps", 30), round(comp.get("duration", 5.0) * comp.get("fps", 30))
    frames = []
    for t in args["times"]:
        f = round(t * fps)
        if f >= frames_in_comp and t <= comp.get("duration", 5.0) + 1e-9:      # the end time is the last frame
            f = frames_in_comp - 1
        if not 0 <= f < frames_in_comp:
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"time {t} s", f"is outside the composition (0 to {(frames_in_comp - 1) / fps:.3f} s, its last frame)")
        frames.append(f)
    return _sheet_of(ctx, doc, comp, sorted(set(frames)), args)


@tools.tool("look_sheet", {"properties": {**ITEM_COMP, **video_frames.VIDEO, "start": {"type": "number", "minimum": 0, "description": "Seconds. Default 0."},
                                           "end": {"type": "number", "minimum": 0, "description": "Seconds. Default (and the comp's duration): the last frame."},
                                           "count": {"type": "integer", "minimum": 2, "maximum": 24, "default": 8, "description": "Frames in the sheet, evenly spaced from start to end."},
                                           "cols": {"type": "integer", "minimum": 1, "maximum": 8, "description": "Tiles per row. Default 4 (fewer when count is small)."},
                                           "width": {"type": "integer", "minimum": 256, "maximum": 2048, "default": SHEET_WIDTH,
                                                     "description": "Width of the whole sheet in px (default 1600: ~390 px tiles 4 across); the tiles share it."}}})
def look_sheet(ctx, args):
    """A contact sheet: `count` frames spread over a time range (`start`, `end` in seconds) in one image `width` px wide,
    each tile labelled with its time and frame, e.g. {"what": "sheet", "start": 2, "end": 5, "count": 12}. Use it to check
    a whole motion at a glance; look_frame for detail. Tiles are drawn at their own size, so a big sheet stays quick.
    For moments you choose (not evenly spaced) give look_frame `times` instead: the same sheet.
    `video`: the path of a finished mp4 (render_video's `video`): the sheet is made of the film's own frames (start / end /
    count in the film's seconds), so you look at the export itself, not the composition."""
    if "video" in args:
        return video_frames.video_sheet(ctx, args, None)
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
