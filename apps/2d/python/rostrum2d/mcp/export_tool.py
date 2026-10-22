"""render_export: any export format of a composition, always a job. The screen's Export button runs the same code (exporting.py)."""
from __future__ import annotations

from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from . import export_name, exporting
from .pick import ITEM_COMP, doc_and_comp

tools = Tools()


@tools.tool("render_export", {"required": ["format"], "properties": {
    **ITEM_COMP,
    "format": {"type": "string", "enum": [r["name"] for r in exporting.formats()],
               "description": "mp4 | prores4444 (alpha) | webm (alpha) | gif | png (a sequence of pictures in a new folder) | lottie (vector JSON; the reply lists what it couldn't carry) | motion (the moving layers' place, scale and opacity 60 times a second: the samples file RostrumSound's edit_sounds_from_motion reads)."},
    "layers": {"type": "array", "items": {"type": "string"}, "description": "motion only: sample these layer ids (a camera as camera:<id>). Default: every layer and camera that moves on its own."},
    "alpha": {"type": "boolean", "description": "Keep transparency. Default: on for the formats that can carry it (not mp4, not lottie)."},
    "depth": {"type": "integer", "enum": [8, 16], "description": "Bits per channel; png only (default 8)."},
    **exporting.QUALITY_ARGS,
    "start": {"type": "number", "minimum": 0, "description": "Seconds. Default 0. Not for lottie or motion (both always hold the whole composition)."},
    "end": {"type": "number", "minimum": 0, "description": "Seconds. Default: the end of the composition. Not for lottie or motion."},
    "path": {"type": "string", "description": "Write here (absolute, or relative to the project folder; for png a new folder). Default: the project's renders folder (a versioned render with a manifest, the file named after the project and composition), or the render cache."},
    "overwrite": {"type": "boolean", "description": "Replace a file that already exists at `path`. Default false: an existing file makes the export fail (nothing is replaced)."}}})
def render_export(ctx, args):
    """Export a composition in one of the formats the Export button offers, through the same engine as look_frame. Always a job: it
    returns a job id at once; ask with inspect_job (wait_s up to 25). The file is written under a .partial name and renamed once it
    read back right (frame count, size, alpha, bit depth); a failure names what failed and leaves nothing under the final name."""
    doc, comp = doc_and_comp(ctx, args)
    fmt = args["format"]
    s = exporting.settings(ctx.tool, fmt, comp.get("duration", 5.0), args.get("alpha"), args.get("depth"), args.get("start"), args.get("end"),
                                args.get("quality"), args.get("bitrate"))
    out = None
    if "path" in args:
        out = Path(args["path"])
        if not out.is_absolute():
            out = Path(doc.folder or ".") / out
    if "layers" in args and fmt != "motion":
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"layers"', "is for format motion only")
    scene = exporting.snapshot(doc, comp["id"], fmt, args.get("layers"))   # the job gets a copy, never the document
    folder, item, seq = ctx.app.folder, doc.item_id, doc.seq
    name, overwrite = export_name.stem_of(doc, comp["id"]), bool(args.get("overwrite"))

    def job_fn(job):
        facts = exporting.run(ctx.tool, scene, fmt, s, folder, item, seq, out, job.progress, name=name, overwrite=overwrite)
        say = f'Exported {comp["id"]} as {fmt}: {facts["frames"]} frames at {facts["fps"]} fps'
        data = {k: facts[k] for k in ("file", "frames", "fps", "alpha", "depth", "checked", "files") if k in facts}
        if "report" in facts:
            say += "; Lottie could not carry: " + ("; ".join(facts["report"]) if facts["report"] else "nothing")
            data["report"] = facts["report"]
        if fmt == "motion":
            say = f'Wrote the motion samples of {comp["id"]}: {len(facts["checked"]["layers"])} moving layers ({", ".join(facts["checked"]["layers"])}), {facts["checked"]["samples"]} samples each at {facts["checked"]["rate"]}/s, to {facts["file"]}. Hand it to RostrumSound: edit_sounds_from_motion samples="{facts["file"]}"'
            return Reply(say + ".", data)
        return Reply(say + ".", data, [Path(f) for f in facts["files"][:50]])

    return ctx.job(f'render_export {comp["id"]} {fmt}', job_fn,
                   key=f"export|{item}|{comp['id']}|{fmt}|{sorted(s.items())}|{seq}|{out}|{overwrite}")
