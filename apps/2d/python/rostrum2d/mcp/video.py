"""render_video: an mp4 of a composition, always a job (CONVENTIONS § 7)."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from . import render
from .files import render_path
from .pick import ITEM_COMP, doc_and_comp

tools = Tools()


@tools.tool("render_video", {"properties": {**ITEM_COMP, "start": {"type": "number", "minimum": 0, "description": "Seconds. Default 0."},
                                            "end": {"type": "number", "minimum": 0, "description": "Seconds. Default: the end of the composition."},
                                            "path": {"type": "string", "description": "Where to write the .mp4 (absolute, or relative to the project folder). Default: the render cache."}}})
def render_video(ctx, args):
    """Export an mp4 (H.264, bt709) of a composition through the same engine as look_frame. Always a job: it returns a job id at once;
    ask with inspect_job (wait_s up to 25). The file is written under a .partial name and renamed only when it is complete."""
    doc, comp = doc_and_comp(ctx, args)
    fps, duration = comp.get("fps", 30), comp.get("duration", 5.0)
    start, end = args.get("start", 0.0), args.get("end", duration)
    if not 0 <= start < end <= duration + 1e-9:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"range {start}–{end} s", f"must satisfy 0 <= start < end <= {duration} (the composition's length)")
    out = render_path(f'{doc.item_id or "doc"}_{comp["id"]}')
    if "path" in args:
        from pathlib import Path
        out = Path(args["path"])
        if not out.is_absolute():
            out = Path(doc.folder or ".") / out
        if out.suffix.lower() != ".mp4":
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'path "{args["path"]}"', "must end in .mp4")
        out.parent.mkdir(parents=True, exist_ok=True)
    scene = render.scene_of(doc, comp["id"])         # the job gets a copy of the scene, never the document

    def job_fn(job):
        info = render.video(ctx.tool, scene, out, start, end, job.progress)
        return Reply(f'Rendered {comp["id"]}: {info["frames"]} frames at {info["fps"]} fps, {start:g}–{end:g} s.',
                     {"frames": info["frames"], "fps": info["fps"], "start": start, "end": end}, [out])

    return ctx.job(f'render_video {comp["id"]} {start:g}-{end:g}s', job_fn, key=f"video|{doc.item_id}|{comp['id']}|{start}|{end}|{doc.seq}|{out}")
