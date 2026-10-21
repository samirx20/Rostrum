"""render_export: any export format of a composition, always a job. The screen's Export button runs the same code (exporting.py)."""
from __future__ import annotations

from pathlib import Path

from rostrum_core.mcp import Reply, Tools

from . import exporting, render
from .pick import ITEM_COMP, doc_and_comp

tools = Tools()


@tools.tool("render_export", {"required": ["format"], "properties": {
    **ITEM_COMP,
    "format": {"type": "string", "enum": [r["name"] for r in exporting.formats()],
               "description": "mp4 | prores4444 (alpha) | webm (alpha) | gif | png (a sequence of pictures in a new folder) | lottie (vector JSON; the reply lists what it couldn't carry)."},
    "alpha": {"type": "boolean", "description": "Keep transparency. Default: on for the formats that can carry it (not mp4, not lottie)."},
    "depth": {"type": "integer", "enum": [8, 16], "description": "Bits per channel; png only (default 8)."},
    "start": {"type": "number", "minimum": 0, "description": "Seconds. Default 0. Not for lottie."},
    "end": {"type": "number", "minimum": 0, "description": "Seconds. Default: the end of the composition. Not for lottie."},
    "path": {"type": "string", "description": "Write here (absolute, or relative to the project folder; for png a new folder). Default: the project's renders folder (a versioned render with a manifest), or the render cache."}}})
def render_export(ctx, args):
    """Export a composition in one of the formats the Export button offers, through the same engine as look_frame. Always a job: it
    returns a job id at once; ask with inspect_job (wait_s up to 25). The file is written under a .partial name and renamed once it
    read back right (frame count, size, alpha, bit depth); a failure names what failed and leaves nothing under the final name."""
    doc, comp = doc_and_comp(ctx, args)
    fmt = args["format"]
    s = exporting.settings(ctx.tool, fmt, comp.get("duration", 5.0), args.get("alpha"), args.get("depth"), args.get("start"), args.get("end"))
    out = None
    if "path" in args:
        out = Path(args["path"])
        if not out.is_absolute():
            out = Path(doc.folder or ".") / out
    scene = render.scene_of(doc, comp["id"])         # the job gets a copy of the scene, never the document
    folder, item, seq = ctx.app.folder, doc.item_id, doc.seq

    def job_fn(job):
        facts = exporting.run(ctx.tool, scene, fmt, s, folder, item, seq, out, job.progress)
        say = f'Exported {comp["id"]} as {fmt}: {facts["frames"]} frames at {facts["fps"]} fps'
        data = {k: facts[k] for k in ("file", "frames", "fps", "alpha", "depth", "checked", "files") if k in facts}
        if "report" in facts:
            say += "; Lottie could not carry: " + ("; ".join(facts["report"]) if facts["report"] else "nothing")
            data["report"] = facts["report"]
        return Reply(say + ".", data, [Path(f) for f in facts["files"][:50]])

    return ctx.job(f'render_export {comp["id"]} {fmt}', job_fn,
                   key=f"export|{item}|{comp['id']}|{fmt}|{sorted(s.items())}|{seq}|{out}")
