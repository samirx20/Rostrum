"""render_video: an mp4 of a composition, always a job (CONVENTIONS § 7)."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

from rostrum_core import project
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_core.mcp.files import render_path

from . import render
from .geometry import comp_size
from .pick import ITEM_COMP, doc_and_comp

tools = Tools()


def manifest(item: str, doc, comp: dict, partial: Path, info: dict, start: float, end: float) -> dict:
    """What the render is (shared/HANDOFFS.md § 5): the first frame is 1001, as for every picture hand-off."""
    fps, first = info["fps"], 1001 + round(start * info["fps"])
    return {"item": item, "version": int(partial.name[1:].split(".")[0]), "kind": "pictures", "format": "mp4",
            "made_by": "agent:rostrum-2d", "made_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": {"document": item, "history_entry": doc.seq, "comp": comp["id"]}, "engine": "rostrum-2d",
            "frames": {"first": first, "last": first + info["frames"] - 1, "fps": f"{fps:g}/1", "start": start, "end": end},
            "size": list(comp_size(comp)), "duration": round(end - start, 6),
            "files": [f'{item}_{comp["id"]}.mp4'], "colour": {"space": "Rec.709 (bt709, display-referred)"},
            "checks": {"frame_count": "ok"}}


@tools.tool("render_video", {"properties": {**ITEM_COMP, "start": {"type": "number", "minimum": 0, "description": "Seconds. Default 0."},
                                            "end": {"type": "number", "minimum": 0, "description": "Seconds. Default: the end of the composition."},
                                            "path": {"type": "string", "description": "Also copy the .mp4 here (absolute, or relative to the project folder), with the project saved beside it as <name>.project/ so other apps can open the film. Default: only the project's renders folder."}}})
def render_video(ctx, args):
    """Export an mp4 (H.264, bt709) of a composition through the same engine as look_frame. Always a job: it returns a job id at once;
    ask with inspect_job (wait_s up to 25). With a project folder it is a project render, renders/<item>/vNNN/ (the mp4 and a
    manifest.json, kind "pictures"), which Sound and the Editor find as the item's latest render; a failed export stays in
    vNNN.partial/ and is never listed. Without a project folder it goes to the render cache."""
    doc, comp = doc_and_comp(ctx, args)
    fps, duration = comp.get("fps", 30), comp.get("duration", 5.0)
    start, end = args.get("start", 0.0), args.get("end", duration)
    if not 0 <= start < end <= duration + 1e-9:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"range {start}–{end} s", f"must satisfy 0 <= start < end <= {duration} (the composition's length)")
    folder, item = ctx.app.folder, doc.item_id
    out = render_path(f'{item or "doc"}_{comp["id"]}')
    copy_to = None
    if "path" in args:
        copy_to = Path(args["path"])
        if not copy_to.is_absolute():
            copy_to = Path(doc.folder or ".") / copy_to
        if copy_to.suffix.lower() != ".mp4":
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'path "{args["path"]}"', "must end in .mp4")
        copy_to.parent.mkdir(parents=True, exist_ok=True)
        if not (folder and item):
            out = copy_to
    scene = render.scene_of(doc, comp["id"], (start, end))     # the job gets a copy of the scene, never the document

    def job_fn(job):
        partial = project.begin_render(folder, item) if folder and item else None
        target = partial / f'{item}_{comp["id"]}.mp4' if partial else out
        info = render.video(ctx.tool, scene, target, start, end, job.progress)
        files = [target]
        if partial:
            if info["frames"] != round((end - start) * info["fps"]):      # fail loudly: the .partial stays, nothing is finished
                raise RostrumError(codes.RENDER_FAILED, ctx.tool, f"the video {target.name}", f'has {info["frames"]} frames, expected {round((end - start) * info["fps"])}', hint=f"Left in {partial}.")
            files = [project.finish_render(partial, manifest(item, doc, comp, partial, info, start, end)) / target.name]
            if copy_to:
                tmp = copy_to.with_name(copy_to.stem + ".partial.mp4")
                shutil.copyfile(files[0], tmp)
                tmp.replace(copy_to)
                files.append(copy_to)
                beside = project.save_beside(folder, item, files[0].parent, copy_to.with_name(copy_to.stem + ".project"))
        said = f" The project is saved beside the copy: {beside}." if partial and copy_to else ""
        return Reply(f'Rendered {comp["id"]}: {info["frames"]} frames at {info["fps"]} fps, {start:g}–{end:g} s.{said}',
                     {"frames": info["frames"], "fps": info["fps"], "start": start, "end": end,
                      "project_copy": str(beside) if said else None}, files)

    return ctx.job(f'render_video {comp["id"]} {start:g}-{end:g}s', job_fn, key=f"video|{doc.item_id}|{comp['id']}|{start}|{end}|{doc.seq}|{out}")
