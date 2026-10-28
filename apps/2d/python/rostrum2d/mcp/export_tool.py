"""render_export: any export format of a composition, always a job. The screen's Export button runs the same code (exporting.py)."""
from __future__ import annotations

import copy
from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from rostrum2d import project_sound

from . import export_area, export_name, exporting, video
from .pick import ITEM_COMP, doc_and_comp

tools = Tools()


@tools.tool("render_export", {"required": ["format"], "properties": {
    **ITEM_COMP,
    "format": {"type": "string", "enum": [r["name"] for r in exporting.formats()],
               "description": "mp4 | prores4444 (alpha) | webm (alpha) | gif | png (a sequence of pictures in a new folder) | lottie (vector JSON; the reply lists what it couldn't carry) | motion (the moving layers' place, scale and opacity 60 times a second: the samples file RostrumSound's edit_sounds_from_motion reads)."},
    "layers": {"type": "array", "items": {"type": "string"}, "description": "motion only: sample these layer ids (the frame as camera:<frame id>). Default: every layer and the frame that moves on its own."},
    "alpha": {"type": "boolean", "description": "Keep transparency. Default: on only for a format that can carry it (not mp4, not lottie) and a transparent composition background."},
    "depth": {"type": "integer", "enum": [8, 16], "description": "Bits per channel; png only (default 8)."},
    **exporting.QUALITY_ARGS,
    **exporting.GIF_ARGS,
    "sound": {"type": "boolean", "description": "mp4 only: put the project's sound under the picture (the scene's soundtrack, else the project's main mix, mixed by RostrumSound's engine and cut to start..end). Default: on for mp4 when the project has sound. If the mix or putting it under the picture fails, the export fails; never a silent file."},
    "time": {"type": "number", "minimum": 0, "description": "png only: one picture at this time (seconds), instead of start / end."},
    **export_area.ARGS,
    "start": {"type": "number", "minimum": 0, "description": "Seconds. Default 0. Not for lottie or motion (both always hold the whole composition)."},
    "end": {"type": "number", "minimum": 0, "description": "Seconds. Default: the end of the composition. Not for lottie or motion."},
    "path": {"type": "string", "description": "Write here (absolute, or relative to the project folder; for png a new folder). Default: the project's renders folder (a versioned render with a manifest, the file named after the project and composition), or the person's Videos folder (no project)."},
    "name": {"type": "string", "description": "The file's name without its type (\"Launch film\" → Launch film.mp4), as the Export panel's name field. Default: the project's name (and the composition's when it says something). Characters a file name can't hold are dropped."},
    "overwrite": {"type": "boolean", "description": "Replace a file that already exists at `path`. Default false: an existing file makes the export fail (nothing is replaced)."}}})
def render_export(ctx, args):
    """Export a composition in one of the formats the Export button offers, through the same engine as look_frame. Always a job: it
    returns a job id at once; ask with inspect_job (wait_s up to 25). The file is written under a .partial name and renamed once it
    read back right (frame count, size, alpha, bit depth); a failure names what failed and leaves nothing under the final name.
    A composition with nothing showing (no layer, or every layer hidden; its frame alone draws nothing) is refused at once,
    before any job, as the Export button refuses it. An mp4's reply ends, as render_video's does, with the time left and the film's
    weakest moments (look_review); `quiet_stretches` and `edge_cuts` carry the file's checks as data."""
    doc, comp = doc_and_comp(ctx, args)
    fmt = args["format"]
    s = exporting.settings(ctx.tool, fmt, comp.get("duration", 5.0), args.get("alpha"), args.get("depth"), args.get("start"), args.get("end"),
                                args.get("quality"), args.get("bitrate"), comp.get("background", "#000000"),
                                project_sound.for_export(doc.folder, comp.get("soundtrack", ""), fmt, args.get("sound")),
                           args.get("size"), args.get("rate"))
    if "time" in args:
        if fmt != "png" or "start" in args or "end" in args:
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"time"', "is for one png picture; it can't go with another format or start / end")
        s["start"], s["end"] = args["time"], min(args["time"] + 1 / comp.get("fps", 30), comp.get("duration", 5.0))
        if not 0 <= s["start"] < s["end"]:
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'time {args["time"]} s', f'is at or past the end ({comp.get("duration", 5.0)} s)')
    s["area"] = export_area.chosen(ctx.tool, fmt, comp, s["start"], args.get("area"), args.get("ids"), args.get("scale"))
    out = None
    if "path" in args:
        out = Path(args["path"])
        if not out.is_absolute():
            out = Path(doc.folder or ".") / out
    if "layers" in args and fmt != "motion":
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, '"layers"', "is for format motion only")
    scene = exporting.snapshot(doc, comp["id"], fmt, args.get("layers"))   # the job gets a copy, never the document
    folder, item, seq = ctx.app.folder, doc.item_id, doc.seq
    name, overwrite = (export_name.clean(args.get("name") or "") or export_name.stem_of(doc, comp["id"])), bool(args.get("overwrite"))
    data_now = copy.deepcopy(doc.data) if fmt == "mp4" else None        # the edge check reads the scene as exported

    def job_fn(job):
        facts = exporting.run(ctx.tool, scene, fmt, s, folder, item, seq, out, job.progress, name=name, overwrite=overwrite, on_stop=job.on_cancel)
        say = f'Exported {comp["id"]} as {fmt}: {facts["frames"]} frames at {facts["fps"]} fps'
        data = {k: facts[k] for k in ("file", "frames", "fps", "alpha", "depth", "checked", "files", "sound") if k in facts}
        if "sound" in facts:
            say += f', with the sound of "{facts["sound"]["song"]}"'
        if "report" in facts:
            say += "; Lottie could not carry: " + ("; ".join(facts["report"]) if facts["report"] else "nothing")
            data["report"] = facts["report"]
        if fmt == "motion":
            say = f'Wrote the motion samples of {comp["id"]}: {len(facts["checked"]["layers"])} moving layers ({", ".join(facts["checked"]["layers"])}), {facts["checked"]["samples"]} samples each at {facts["checked"]["rate"]}/s, to {facts["file"]}. Hand it to RostrumSound: edit_sounds_from_motion samples="{facts["file"]}"'
            return Reply(say + ".", data)
        if fmt == "mp4":            # the same checks as render_video's reply, on the finished file
            quiet = video._quiet_stretches(Path(facts["file"]), s["start"])
            cuts = video._edge_cuts(data_now, next(c for c in data_now["comps"] if c["id"] == comp["id"]), s["start"], s["end"])
            data.update(quiet_stretches=quiet[1], edge_cuts=cuts[1])
            say += '. ' + exporting.next_steps(f'look_frame what "sheet" with video "{facts["file"]}"', "sound" in facts, folder).rstrip(".")
        return Reply(say + ".", data, [Path(f) for f in facts["files"][:50]])

    return ctx.job(f'render_export {comp["id"]} {fmt}', job_fn,
                   key=f"export|{item}|{comp['id']}|{fmt}|{sorted(s.items(), key=str)}|{seq}|{out}|{overwrite}")
