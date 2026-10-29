"""render_video: an mp4 of a composition, always a job (CONVENTIONS § 7)."""
from __future__ import annotations

import copy
import shutil
import time
from pathlib import Path

from rostrum_core import project
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools, faults
from rostrum_core.mcp.files import render_path

from rostrum2d import project_sound

from . import edge_cut, exporting, film_faults, look_empty, render
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


def _quiet_stretches(mp4: Path, start: float) -> tuple[str, list]:
    """The empty / washed-out / unchanged stretches of the finished file (look_empty), as a sentence and rows. A check that
    fails says so in the reply: the export itself still stands."""
    try:
        rows = look_empty.scan_video(mp4, start)
    except Exception as e:      # noqa: BLE001  (the render is done; the check's failure is reported, not hidden)
        return f"(The empty-stretch check could not run: {e}.)", []
    if not rows:
        return "No empty, washed-out or unchanged stretch found.", []
    return look_empty.tell(rows, start, start).replace("Stretches to look at", "Stretches to check").replace("look_frame at those times", "look_frame at those times (look_frame what \"empty\" re-checks)"), rows


def _edge_cuts(data: dict, comp: dict, start: float, end: float) -> tuple[str, list]:
    """Subjects cut by the frame edge across the render (edge_cut, every look_empty.EVERY s), from the scene as rendered."""
    try:
        times = [start + i * look_empty.EVERY for i in range(int((end - start) / look_empty.EVERY + 1e-9))]
        rigs, _ = edge_cut.rig_boxes(data, comp, times)
        rows = edge_cut.scan(comp, times, rigs, look_empty.EVERY)
    except Exception as e:      # noqa: BLE001  (the render is done; the check's failure is reported, not hidden)
        return f"(The frame-edge check could not run: {e}.)", []
    return edge_cut.tell(rows), rows


def checked(job, frames: int, mp4: Path, shown: Path, data: dict, comp: dict, start: float, end: float) -> tuple:
    """The finished file's checks (quiet stretches, edge cuts), run after it is delivered and saying so in the job's
    progress: the showreel's finished export sat at "2400 of 2400, nothing new" while they ran, its file not yet copied."""
    job.progress(frames, frames, f"The video is written ({shown}). Checking it for empty stretches.")
    quiet = _quiet_stretches(mp4, start)
    job.progress(frames, frames, f"The video is written ({shown}). Checking it for subjects cut by the frame edge.")
    return quiet, _edge_cuts(data, comp, start, end)


@tools.tool("render_video", {"properties": {**ITEM_COMP, "start": {"type": "number", "minimum": 0, "description": "Seconds. Default 0."},
                                            "end": {"type": "number", "minimum": 0, "description": "Seconds. Default: the end of the composition."},
                                            **exporting.QUALITY_ARGS,
                                            "sound": {"type": "boolean", "description": "Put the project's sound under the picture, as render_export's mp4 does (the scene's soundtrack, else the project's main mix; the song is mixed afresh from its current document, cached while it is unchanged, so no render_mix is needed first). Default: on when the project has sound. If the mix fails, the render fails; never a silent file."},
                                            "path": {"type": "string", "description": "Also copy the .mp4 here (absolute, or relative to the project folder; only the mp4 is written there unless `with_project` is true). Default: only the project's renders folder."},
                                            "overwrite": {"type": "boolean", "description": "Accepted so a call with it works; has no effect. A project render always goes to a new version folder, and a `path` copy always replaces the file already there."},
                                            "with_project": {"type": "boolean", "description": "With `path`: also save the project beside the copy as <name>.project/ so another machine or app can open the film. Default false: just the mp4."},
                                            "keep": {**faults.KEEP["keep"], "description": "The whole film is a final: refused while a fault is open (the files kept as <name>.NOT-DONE.mp4). Explain each fault you leave on purpose, {fault_id: \"why\"}, the why quoting the brief's words that ask for it (brief(\"...\") in the script)."}}})
def render_video(ctx, args):
    """Export an mp4 (H.264, bt709) of a composition through the same engine as look_frame. It waits for its job in this call (wait_s,
    default 120 s) and answers with the finished file; past that it answers with the job id:
    ask with inspect_job (wait_s up to 25): frames done of total and how long since the last one. A frame stuck over 2 minutes
    fails the job with an error naming the frame; run_stop ends it at once, from this or another session. With a project folder it is a project render, renders/<item>/vNNN/ (the mp4 and a
    manifest.json, kind "pictures"), which Sound and the Editor find as the item's latest render; a failed export stays in
    vNNN.partial/ and is never listed. Without a project folder it goes to the person's Videos folder. The finished reply
    names the deliverable (`video`: the `path` copy when given, else the render) and says whether it has sound (`has_sound`). It also checks the finished file (blank, washed-out and unchanged stretches: `quiet_stretches`; subjects cut by the frame edge: `edge_cuts`) and ends with the time left and the film's weakest moments with times, ranked (look_review): fix the top one and export again.
    `beats`: the brief's timed beats, kept for the session; every export then names one that never happens or comes too soon.
    Faults first, as render_export's file formats: the reply opens NOT DONE: with each fault and its fix, or DONE:; the whole
    film is a final, refused while a fault is open (kept as <name>.NOT-DONE.mp4) unless `keep` explains each by quoting the
    brief; a part (start / end) is a preview, never refused."""
    doc, comp = doc_and_comp(ctx, args)
    fps, duration = comp.get("fps", 30), comp.get("duration", 5.0)
    s = exporting.settings(ctx.tool, "mp4", duration, start=args.get("start"), end=args.get("end"), quality=args.get("quality"), bitrate=args.get("bitrate"),
                           sound=project_sound.for_export(doc.folder, comp.get("soundtrack", ""), "mp4", args.get("sound")))
    start, end = s["start"], s["end"]
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
    whole = start <= 0 and end >= duration - 1e-9        # the whole film is a deliverable: a 3D layer not rendered yet refuses (scene.describe)
    scene = render.scene_of(doc, comp["id"], None if whole else (start, end))     # the job gets a copy of the scene, never the document
    data = copy.deepcopy(doc.data)
    comp_now = next(c for c in data["comps"] if c["id"] == comp["id"])

    def job_fn(job):
        partial = project.begin_render(folder, item) if folder and item else None
        target = partial / f'{item}_{comp["id"]}.mp4' if partial else out
        info = render.video(ctx.tool, scene, target, start, end, job.progress, s["quality"], s["bitrate"], job.on_cancel)
        exporting.with_sound(ctx.tool, info, target, s, folder or doc.folder)      # before it is finished or copied
        files, beside = [target], None
        if partial:
            if info["frames"] != round((end - start) * info["fps"]):      # fail loudly: the .partial stays, nothing is finished
                raise RostrumError(codes.RENDER_FAILED, ctx.tool, f"the video {target.name}", f'has {info["frames"]} frames, expected {round((end - start) * info["fps"])}', hint=f"Left in {partial}.")
            files = [project.finish_render(partial, manifest(item, doc, comp, partial, info, start, end)) / target.name]
            if copy_to:
                tmp = copy_to.with_name(copy_to.stem + ".partial.mp4")
                shutil.copyfile(files[0], tmp)
                tmp.replace(copy_to)
                files.append(copy_to)
                beside = args.get("with_project") and project.save_beside(folder, item, files[0].parent, copy_to.with_name(copy_to.stem + ".project"))
        quiet, cuts = checked(job, info["frames"], files[0], files[-1], data, comp_now, start, end)    # delivered first
        found, notes = film_faults.of_export(data, comp_now, start, end, ctx.tool, [dict(q) for q in quiet[1]], cuts[1])
        if whole:                   # a final: open faults hold every file back as <name>.NOT-DONE.mp4 and this raises
            notes += film_faults.deliver(found, args.get("keep"), data, ctx.tool, files)
        said = f" The project is saved beside the copy: {beside}." if partial and copy_to and beside else ""
        took = info["timing"]["totalS"]
        video = files[-1] if len(files) > 1 else files[0]           # the deliverable: the copy asked for, else the render
        heard = (f"with sound (the project's mix{', song ' + str(info['sound']['song']) if info['sound'].get('song') else ''}, "
                 "checked present in the file)" if info.get("sound") else "silent (no sound track: the project has no "
                 "sound, or sound was off)")
        also = f" The same video is kept as the project's render {files[0]}." if len(files) > 1 else ""
        return Reply(f'Rendered {comp["id"]}: {info["frames"]} frames at {info["fps"]} fps, {start:g}–{end:g} s, in {took // 60:.0f} min {took % 60:02.0f} s '
                     f'on {info.get("adapter") or "the processor"}. The video: {video}, {heard}.{also}{said} '
                     f'{exporting.next_steps(f'look_frame what "sheet", start {start:g}, end {end:g}', bool(info.get("sound")), folder or doc.folder)}',
                     {"video": str(video), "has_sound": bool(info.get("sound")),
                      "frames": info["frames"], "fps": info["fps"], "start": start, "end": end, "sound": info.get("sound"),
                      **({"project_copy": str(beside)} if said else {}), "seconds": round(took, 1), "adapter": info.get("adapter"),
                      "timing": info["timing"], "workers": info.get("workers"), "quiet_stretches": quiet[1], "edge_cuts": cuts[1]}, files,
                     warnings=scene.get("warnings", []) + [w for w in [info.get("warning")] if w] + notes, faults=found)

    return ctx.job(f'render_video {comp["id"]} {start:g}-{end:g}s', job_fn, key=f"video|{doc.item_id}|{comp['id']}|{start}|{end}|{s['quality']}|{s['bitrate']}|{s['sound']}|{doc.seq}|{out}|{args.get('with_project')}")
