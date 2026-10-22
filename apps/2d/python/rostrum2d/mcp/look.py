"""look_frame and look_sheet: the agent's eyes on the picture, drawn by the same engine as export (preview ≡ export)."""
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


def shown_ids(comp: dict, t: float) -> list[str]:
    w, h = comp_size(comp)
    return [n["id"] for n in flatten(comp, t) if n["type"] != "group" and not problems_showing(n, w, h)]


@tools.tool("look_frame", {"properties": {**ITEM_COMP, **TIME, "width": {"type": "integer", "minimum": 64, "maximum": 4096, "default": FRAME_WIDTH,
                                                                          "description": "Picture width in px (never larger than the composition). Default 960."}}})
def look_frame(ctx, args):
    """One rendered frame of a composition at a time (seconds) or frame number, as a PNG file and as an image you can see.
    Also lists which layers are on screen then (approximate: judged from their values, not from pixels)."""
    doc, comp = doc_and_comp(ctx, args)
    t, frame = time_of(ctx, comp, args)
    scene, width = render.scene_of(doc, comp["id"], (t, t)), args.get("width", FRAME_WIDTH)
    dest = look_path(f'{doc.item_id or "doc"}_{comp["id"]}_f{frame}')
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


@tools.tool("look_sheet", {"properties": {**ITEM_COMP, "start": {"type": "number", "minimum": 0, "description": "Seconds. Default 0."},
                                           "end": {"type": "number", "minimum": 0, "description": "Seconds. Default: the last frame."},
                                           "count": {"type": "integer", "minimum": 2, "maximum": 24, "default": 8, "description": "Frames in the sheet, evenly spaced from start to end."},
                                           "cols": {"type": "integer", "minimum": 1, "maximum": 8, "description": "Tiles per row. Default 4 (fewer when count is small)."},
                                           "width": {"type": "integer", "minimum": 64, "maximum": 1280, "default": 480, "description": "Width of each tile in px."}}})
def look_sheet(ctx, args):
    """A contact sheet: `count` frames spread over a time range in one image, each tile labelled with its time and frame.
    Use it to check a whole motion at a glance; look_frame for detail."""
    doc, comp = doc_and_comp(ctx, args)
    fps, duration = comp.get("fps", 30), comp.get("duration", 5.0)
    last = (round(duration * fps) - 1) / fps
    start, end, count = args.get("start", 0.0), args.get("end", last), args.get("count", 8)
    if not 0 <= start < end <= last + 1e-9:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'range {start}–{end} s', f"must satisfy 0 <= start < end <= {last:.3f} (the last frame)")
    frames = sorted({round((start + (end - start) * i / (count - 1)) * fps) for i in range(count)})
    scene, tile_w = render.scene_of(doc, comp["id"], (frames[0] / fps, frames[-1] / fps)), args.get("width", 480)
    cols = args.get("cols", min(4, len(frames)))
    dest = look_path(f'{doc.item_id or "doc"}_{comp["id"]}_sheet')

    def job_fn(job):
        with tempfile.TemporaryDirectory(prefix="rostrum_sheet_") as tmp:
            items = [(f / fps, Path(tmp) / f"f{f}.png") for f in frames]
            render.stills(ctx.tool, scene, items, job.progress)
            tiles = [(png, f"{t:.2f} s   f{f}") for (t, png), f in zip(items, frames)]
            w, h = sheet.contact_sheet(tiles, tile_w, cols, dest)
        return Reply(f'Contact sheet of {comp["id"]}: {len(frames)} frames from {frames[0] / fps:.2f} to {frames[-1] / fps:.2f} s, {w}×{h}.',
                     {"frames": frames, "times": [round(f / fps, 4) for f in frames], "width": w, "height": h, "cols": cols}, [dest], [dest],
                     scene.get("warnings", []))

    return ctx.long(f'look_sheet {comp["id"]}', job_fn)
