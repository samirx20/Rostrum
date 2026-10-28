"""render_still and render_video: pictures for the Editor and the world, always jobs (CONVENTIONS § 7).

A render is a project version `renders/<item>/vNNN/` (the files and a manifest.json, kind "pictures"); a failed one stays in
`vNNN.partial/` and is never listed. A stopped still (cancelled on purpose) leaves nothing (`kept_unless_stopped`); a stopped or
failed shot render (render_video, mcp/sequence.py) keeps the frames it finished, and the same render asked for again continues
from them (mcp/resume.py). Without a project folder it goes to the render cache. The engine writes each picture to
`<name>.partial` and renames it, so every file is whole; the video is encoded by the `ffmpeg` program (a separate process,
like 2D's) from the PNG frames and written whole or not at all, with a small share copy `<name>-share.mp4` beside it (`share_copy`).
"""
from __future__ import annotations

import contextlib
import copy
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from rostrum_core import project
from rostrum_core.storage import doc_hash
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_core.mcp.files import render_cache_folder

from ..render_fields import QUALITIES, STYLIZED
from ..sim.compute import ready_for_render
from ..sim.fall_view import fall_note             # a fall the shot camera does not show
from ..faults import shot_faults                  # parts apart, floating, cut by the frame edge
from .. import estimate_job, estimate_learn, render_last
from . import draw, estimate, layers, resume
from .shot import ITEM_SHOT, QUALITY, RENDERERS, TIME, check_frame, doc_and_shot, frame_of, render_settings, renderer_of, seconds, size_of

tools = Tools()
FIRST = 1001                                   # the first frame of every picture hand-off (shared/HANDOFFS.md § 6)
QUALITY_ARG = {"enum": list(QUALITY), "description": "final = Cycles (path traced), fast = Storm (a draft). Default: the shot's render Quality "
                                                    "(Stylized there renders Stylized, every other Quality renders Final)."}
SETTINGS = {
    "renderer": {"enum": list(RENDERERS), "description": "Overrides quality: storm, cycles or stylized (materials' Lines, Halftone and Light to colour; drawn at twice the size and smoothed down; no passes)."},
    "width": {"type": "integer", "minimum": 64, "maximum": 8192, "description": "Picture width in px. Default: the shot's render size (renderSize); the height follows."},
    "samples": {"type": "integer", "minimum": 1, "maximum": 8192, "description": "Cycles samples per pixel. Default: the shot's render quality (draft 32, good 128, final 512)."},
    "denoise": {"type": "boolean", "description": "Cycles noise clean-up. Default: the shot's render settings (on)."},
    "exposure": {"type": "number", "default": 0, "description": "Stops, applied to the PNG only (the EXR stays scene-linear)."},
    "passes": layers.PASSES_ARG,
}


@dataclass(frozen=True)
class DocView:
    """What a render reads of a document, frozen when the render is asked for: the item, the history step and a copy of the data
    (so edits made while it runs are not in it, and its manifest says exactly which state it shows). The one view both the tools
    and the screen's Render button hand to `still`: never a stripped-down stand-in, so a field the manifest needs can't be missing."""
    item_id: str
    seq: int
    data: dict

    @classmethod
    def of(cls, doc) -> "DocView":
        return doc if isinstance(doc, cls) else cls(doc.item_id, doc.seq, copy.deepcopy(doc.data))


def _renderer(args: dict, s: dict) -> str:
    """The call's renderer, else its quality, else the shot's render Quality (render_fields.settings: stylized or cycles)."""
    return renderer_of(args) if "renderer" in args or "quality" in args else s["renderer"]


def _cycles(args: dict, renderer: str, s: dict) -> dict:
    """The renderer's own request settings. Cycles: samples and noise clean-up, the call's, else the shot's render
    settings (render_fields.settings; a shot set to Stylized: the Final preset's). Stylized: its supersampling."""
    if renderer == "stylized":
        return {"stylized": dict(STYLIZED)}
    if renderer != "cycles":
        return {}
    s = s if s["renderer"] == "cycles" else QUALITIES["final"]
    return {"samples": args.get("samples", s["samples"]), "denoise": args.get("denoise", s["denoise"])}


def _shot(doc, info: dict) -> dict:
    return next(x for x in doc.data["shots"] if x["id"] == info["id"])


def _manifest(item, doc, info, partial: Path, renderer: str, size, frames: list[int], files: list[str], first_file: int,
              channels: list[str] | None = None) -> dict:
    """The render's manifest; `channels` (the core's reply, when an EXR was written) adds what the EXR's layers are."""
    fps = info["fps"]
    return {"item": item, "version": int(m.group(1)) if (m := re.match(r"^v(\d+)\.partial$", partial.name)) else 0, "kind": "pictures",
            "made_by": "agent:rostrum-3d", "made_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": {"document": item, "history_entry": doc.seq, **_hashes(doc.data), "shot": info["id"], "camera": info["camera"]},
            "engine": f"rostrum-3d ({renderer})", "frames": {"first": first_file, "last": first_file + len(frames) - 1, "fps": f"{fps:g}/1",
                                                            "shot_frames": [frames[0], frames[-1]]},
            "size": list(size), "colour": {"space": "scene-linear Rec.709 (EXR), sRGB display (PNG, OpenColorIO)"},
            "files": files, "checks": {"frame_count": "ok", "readable": "ok"},
            **({"exr": layers.describe(channels, doc.data)} if channels else {})}


def _hashes(data: dict) -> dict:
    """The scene as rendered, by content: `scene_hash` is what 2D and the Editor compare with the 3D document's hash now
    (SPEC §12); the hash of the whole document, so any change to it marks the render out of date. `doc_hash` is the same
    value under its older name, for readers of renders made before scene_hash."""
    h = doc_hash(data)
    return {"scene_hash": h, "doc_hash": h}


def resumable_folder(folder, doc, info, key: str) -> tuple[Path, bool]:
    """The kept .partial folder of this very shot render (same hash, resume.find), else a new one marked with the hash.
    (path, is a project version)"""
    kept = resume.find(folder, doc.item_id, f'{doc.item_id or "doc"}_{info["id"]}', key)
    if kept is not None:
        return kept, bool(folder and doc.item_id)
    partial, is_version = _folder(folder, doc, info)
    resume.mark(partial, key)
    return partial, is_version


def _folder(folder, doc, info) -> tuple[Path, bool]:
    """A new empty .partial folder: the project's next version, or the render cache. (path, is a project version)"""
    if folder and doc.item_id:
        return project.begin_render(folder, doc.item_id), True
    return render_cache_folder(f'{doc.item_id or "doc"}_{info["id"]}'), False


@contextlib.contextmanager
def kept_unless_stopped(partial: Path, stopped=None):
    """Around a one-picture render into `partial`: when it raises because it was stopped on purpose (`stopped()` true: a cancel),
    the half-made folder goes, since nobody wants it; a real failure keeps it (the error names it) to look at. (A shot
    render keeps its finished frames instead: resume.keeps_frames.)"""
    try:
        yield
    except BaseException:
        if stopped is not None and stopped():
            shutil.rmtree(partial, ignore_errors=True)
        raise


def _finish(partial: Path, is_version: bool, manifest: dict) -> Path:
    if is_version:
        return project.finish_render(partial, manifest)
    done = partial.with_name(partial.name[:-len(".partial")])
    partial.rename(done)
    return done


def _renumber(folder: Path, name: str, ext: str, start: int, first_file: int):
    """name.<shot frame>.ext -> name.<FIRST + n>.ext (4 digits at least), so the files follow the hand-off numbering."""
    for f in sorted(folder.glob(f"{name}.*.{ext}"), reverse=first_file > start):
        n = int(f.name[len(name) + 1:-len(ext) - 1])
        f.rename(f.with_name(f"{name}.{first_file + n - start:04d}.{ext}"))


def still(where: str, doc, info: dict, scene: dict, engine, frame: int, renderer: str, size: tuple[int, int], formats: list[str],
          exposure: float = 0, settings: dict | None = None, folder=None, passes: list[str] | None = None, stopped=None,
          step=None) -> tuple[Path, list[Path], dict]:
    """One picture of a shot frame through its camera, as a whole project render version (or in the render cache without a
    project folder). The one code path of the render_still tool and the 3D screen's Render button. Blocking: call it from a job.
    Returns (the finished folder, its files, the engine's reply); a failure raises RENDER_FAILED and leaves only a .partial
    (`stopped()`: the caller cancelled it, so not even that). `step(line)`: how far Cycles has got (Engine.render)."""
    doc = DocView.of(doc)
    scene = ready_for_render(where, doc.data, info["id"], folder, scene)     # a falling thing: its simulation, computed first if needed
    partial, is_version = _folder(folder, doc, info)
    item, (w, h) = doc.item_id, size
    name = f'{item or "doc"}_{info["id"]}_f{frame:04d}'
    req = {f: str(partial / f"{name}.{f}") for f in formats}
    with kept_unless_stopped(partial, stopped):
        out = draw.render(where, f"frame {frame} of {info['id']}", engine, scene, camera=info["camera"], renderer=renderer, frame=frame,
                          width=w, height=h, exposure=exposure, step=step, **req, **(settings or {}), **({"passes": passes} if passes else {}))
    done = _finish(partial, is_version, _manifest(item, doc, info, partial, renderer, (w, h), [frame], [Path(p).name for p in req.values()], FIRST,
                                                  out.get("channels")))
    return done, [done / Path(p).name for p in req.values()], out


@tools.tool("render_still", {"properties": {**ITEM_SHOT, **TIME, "quality": QUALITY_ARG, **SETTINGS,
                                             "formats": {"type": "array", "items": {"enum": ["png", "exr"]}, "minItems": 1, "uniqueItems": True,
                                                         "default": ["png", "exr"], "description": "png = 8-bit sRGB picture, exr = scene-linear half-float for the Editor."}}})
def render_still(ctx, args):
    """One final picture of a shot through the shot camera (the shot's render Quality by default: Cycles, or Stylized when the Quality is Stylized), as a project render with a manifest: png (sRGB, through
    OpenColorIO) and/or exr (scene-linear, for the Editor; its passes as named layers, listed in the manifest's `exr`). Always a job: it returns a job id at once; ask with inspect_job (wait_s up to 25), whose note shows how far Cycles has got and the time left measured on this frame ("drawing 40% · about 12 s left")."""
    doc, info = doc_and_shot(ctx, args)
    scene, doc = draw.scene_of(doc, info["id"]), DocView.of(doc)
    frame, s = frame_of(ctx, info, args), render_settings(doc, info)
    renderer = _renderer(args, s)
    w, h = size_of(info, args, s["width"])
    formats = args.get("formats", ["png", "exr"])
    passes = layers.chosen(ctx.tool, args, _shot(doc, info), renderer, "exr" in formats)
    engine, item = draw.engine_of(ctx), doc.item_id

    def job_fn(job):
        first = []

        def drawn(line):                     # Cycles' share of the frame so far: the time left, at the rate since its first report
            f, ms = line["fraction"], line["ms"]
            f0, ms0 = (first or first.append((f, ms)) or first)[0]
            left = f" · about {(ms - ms0) / (f - f0) * (1 - f) / 1000:.0f} s left" if f - f0 >= 0.03 and ms - ms0 >= 800 else ""
            job.progress(round(f * 100), 100, f"drawing {f:.0%}{left}")
        done, files, out = still(ctx.tool, doc, info, scene, engine, frame, renderer, (w, h), formats, args.get("exposure", 0),
                                 _cycles(args, renderer, s), ctx.app.folder, passes, step=drawn)
        return Reply(f'Rendered frame {frame} ({seconds(info, frame):.3f} s) of {info["id"]}: {w}×{h}, {renderer}, {out["frames"][0]["ms"] / 1000:.1f} s.',
                     {"frame": frame, "time": seconds(info, frame), "renderer": out.get("renderer", renderer), "timing": out.get("timing", {}),
                      "vram": out.get("vram", {}), "folder": str(done)}, files, warnings=engine.take_notices())

    return ctx.job(f'render_still {info["id"]} f{frame}', job_fn, key=f"still|{item}|{info['id']}|{frame}|{renderer}|{w}|{args}|{doc.seq}")


@tools.tool("render_video", {"properties": {**ITEM_SHOT, "quality": QUALITY_ARG, **SETTINGS,
                                             "start": {"type": "number", "minimum": 0, "description": "Seconds from the start of the shot. Default 0."},
                                             "end": {"type": "number", "minimum": 0, "description": "Seconds from the start of the shot (the frame at this time is the last one). Default: the last frame of the shot."},
                                             "exr": {"type": "boolean", "default": False, "description": "Also keep every frame as scene-linear EXR next to the mp4 (what the Editor wants), with its passes as layers (passes)."},
                                             "output_folder": {"type": "string", "description": "A folder (absolute path) to copy the finished mp4 and its share copy into, besides the project render. Made if missing; checked before rendering: a folder that can't be written fails at once."},
                                             "file_name": {"type": "string", "description": "The copy's name in output_folder (\".mp4\" optional; its share copy is <name>-share.mp4). Default: the render's own name. A file already there is replaced."},
                                             "budget_min": {"type": "number", "exclusiveMinimum": 0, "description": "Minutes you can spend. The time is measured first (render_estimate's probe, kept for the scene); if the estimate is over this, nothing is rendered and the error names settings that should fit, each with its time."},
                                             "estimate_only": {"type": "boolean", "default": False, "description": "Return the measured estimate (render_estimate's probe of the middle frame, kept for the scene) and render no video."}}})
def render_video(ctx, args):
    """An mp4 (H.264, bt709) of a shot, or of a time range of it, through the shot camera: every frame is rendered (the shot's render Quality by default:
    Cycles, or Stylized when the Quality is Stylized; quality fast = Storm for a draft), then encoded by ffmpeg, plus a small share copy
    `<name>-share.mp4` beside it (about 8 Mbit/s at 1920×1080, scaled by the picture's size). A project render with a manifest; `exr` keeps the EXR frames too;
    `output_folder` (+ `file_name`) also copies the mp4 and its share copy there. A stopped or failed render keeps the frames it finished: the same call
    again (nothing rendered changed) continues from them and draws only the missing frames; the reply says "Continues from N finished frames". Always a
    job: returns a job id at once; ask with inspect_job (wait_s up to 25), which shows 'frame n of m'. With `budget_min` or `estimate_only` the reply waits
    (up to 25 s) for the measured estimate: over the budget it is an error at once that names the settings that fit, and `estimate_only` returns the figures
    (never a failed job), also when over the budget. With no quality, renderer or samples it never renders lower than your
    last export of this shot (a refine keeps the first video's Cycles and samples even if the shot's Quality is lower) and says so;
    asking for lower is done, and the reply says what it loses (Storm: no fabric sheen, no soft bounce light). Also, only when one exists, names faults a client would see (worst first, a few at most, from the document on about ten frames, nothing extra rendered): a part that separates from the figure it was joined to, a thing that floats above what is under it while holding its height (cm), a main subject cut by the frame edge or leaving the frame (which edge, from when), as warnings."""
    gate = Gate() if "budget_min" in args or args.get("estimate_only") else None
    reply = ctx.job(*video_job(ctx, args, gate))
    if gate is None or not gate.wait(ESTIMATE_WAIT_S):
        return reply
    if gate.error is not None:
        raise gate.error
    return gate.reply or reply


ESTIMATE_WAIT_S = 25.0


class Gate:
    """What render_video's budget / estimate_only wait for: the job's estimate is decided (a refusal, the estimate_only figures, or
    "go ahead") while the job itself goes on. Then the tool's reply is that answer at once, not a job to ask about later."""

    def __init__(self):
        self.error: RostrumError | None = None
        self.reply: Reply | None = None
        self._decided = threading.Event()

    def decide(self, error: RostrumError | None = None, reply: Reply | None = None):
        self.error, self.reply = error, reply
        self._decided.set()

    def decided(self) -> bool:
        return self._decided.is_set()

    def wait(self, seconds: float) -> bool:
        return self._decided.wait(seconds)


def next_steps(count: int, fps: float, item: str) -> str:
    """What a finished video's reply says next: a concrete look-and-fix pass with the 3D look tools (the clock line after it
    says how many such passes the time left allows). In the benchmark agents quit after the first video with most of their time unused."""
    return (f"Next, a fix pass: look at it again, now with the look tools: look_sheet (all {count} frames at {fps:g} fps, the whole move), look_frame at its weakest "
            "times (renderer cycles for the final look), look_at on a spot you doubt, look_motion for what moves; name its three weakest moments "
            "(something cut off or hidden, a pose or move that reads stiff, a surface or light that looks flat, an empty stretch), fix each with "
            f"run_script and {item} again with the same output name.")


def _out_target(where: str, args: dict) -> Path | None:
    """render_video's output_folder/file_name as the mp4 path to copy to, checked writable now (fail loudly), or None."""
    if "output_folder" not in args:
        if "file_name" in args:
            raise RostrumError(codes.BAD_ARGUMENT, where, "file_name", "needs output_folder (the folder to copy the mp4 into)")
        return None
    d = Path(os.path.expandvars(os.path.expanduser(args["output_folder"])))
    if not d.is_absolute():
        raise RostrumError(codes.BAD_ARGUMENT, where, f"output_folder {args['output_folder']!r}", "must be an absolute path")
    name = args.get("file_name", "").strip()
    if name and (re.search(r'[\\/:*?"<>|\x00-\x1f]', name) or name.strip(". ") == ""):
        raise RostrumError(codes.BAD_ARGUMENT, where, f"file_name {name!r}", 'must be a plain file name (no folder, none of \\ / : * ? " < > |)')
    try:
        d.mkdir(parents=True, exist_ok=True)
        probe = d / f".rostrum3d-write-check-{os.getpid()}"
        probe.write_bytes(b"")
        probe.unlink()
    except OSError as e:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"output_folder {str(d)!r}", f"can't be written: {e.strerror or e}",
                           hint="Nothing was rendered. Pick a folder you can write to.") from e
    return d / (name if name.lower().endswith(".mp4") else f"{name}.mp4") if name else d


def _copy_out(where: str, mp4: Path, share: Path, target: Path) -> list[Path]:
    """The finished mp4 and its share copy, copied to `target` (a folder: under their own names). Fails loudly."""
    out = target / mp4.name if target.is_dir() else target
    pairs = [(mp4, out), (share, out.with_name(out.stem + "-share.mp4"))]
    try:
        for src, dst in pairs:
            part = dst.with_name(dst.name + ".partial")
            shutil.copyfile(src, part)
            part.replace(dst)
    except OSError as e:
        raise RostrumError(codes.RENDER_FAILED, where, f"the copy to {out.parent}", f"could not be written: {e.strerror or e}",
                           hint=f"The video itself is finished in {mp4.parent}.") from e
    return [dst for _, dst in pairs]


def video_key(scene: dict, info: dict, f0: int, f1: int, renderer: str, size, cycles: dict, exposure: float, keep_exr: bool, passes) -> str:
    """The hash a kept video render is matched by (resume.key_of; a video's frames are PNGs in `_png`, its EXRs beside)."""
    return resume.key_of(scene, info, f0, f1, renderer, size, {**cycles, "exposure": exposure, "video": True},
                         ["png", *(["exr"] if keep_exr else [])], passes if keep_exr else None)


def kept_count(folder, doc, info, key: str, f0: int, f1: int, keep_exr: bool) -> int:
    """How many finished frames the same video render left (0: none kept, it starts afresh)."""
    name = f'{doc.item_id or "doc"}_{info["id"]}'
    kept = resume.find(folder, doc.item_id, name, key)
    return len(resume.finished({"png": kept / "_png", **({"exr": kept} if keep_exr else {})}, name, f0, f1)) if kept else 0


def video(where: str, doc, info: dict, scene: dict, engine, size: tuple[int, int], renderer: str, cycles: dict, f0: int, f1: int,
          folder=None, exposure: float = 0, keep_exr: bool = False, passes: list[str] | None = None, progress=None, stopped=None,
          resumed=None, say=None) -> tuple[Path, list[Path], dict]:
    """Frames f0..f1 of the shot as an mp4 (+ its share copy, + the EXRs with `keep_exr`), as one project render version (or in
    the render cache): the one code path of render_video and the render sheet's MP4. `scene`: as described (before its
    simulation is laid over it; that is what the kept frames are matched by). `progress(done, total)` as frames land (kept
    ones count as done); `resumed(n)` once with the finished frames it continues from; `say(words)` when it starts encoding.
    A stop or failure keeps the finished frames (resume.py). Blocking. Returns (the finished folder, [mp4, share, exrs…], the engine's reply)."""
    doc, fps, (w, h) = DocView.of(doc), info["fps"], size
    passes = passes if passes and keep_exr else None
    key = video_key(scene, info, f0, f1, renderer, size, cycles, exposure, keep_exr, passes)
    scene = ready_for_render(where, doc.data, info["id"], folder, scene)     # its simulation, computed first if needed
    partial, is_version = resumable_folder(folder, doc, info, key)
    name = f'{doc.item_id or "doc"}_{info["id"]}'
    mp4, pngs = partial / f"{name}.mp4", partial / "_png"
    pngs.mkdir(exist_ok=True)
    where_of = {"png": pngs, **({"exr": partial} if keep_exr else {})}
    have = resume.finished(where_of, name, f0, f1, tidy=True)
    if resumed:
        resumed(len(have))
    req = {"png": str(pngs / f"{name}.{{frame}}.png"), **({"exr": str(partial / f"{name}.{{frame}}.exr")} if keep_exr else {})}
    with resume.keeps_frames(partial, lambda: len(resume.finished(where_of, name, f0, f1)), stopped):
        out = resume.render_missing(where, f"frames {f0}–{f1} of {info['id']}", engine, scene, f0, f1, have, progress,
                                    camera=info["camera"], renderer=renderer, width=w, height=h, exposure=exposure, timeoutS=3600,
                                    **req, **cycles, **({"passes": passes} if passes else {}))
        got = resume.finished(where_of, name, f0, f1)
        if len(got) != f1 - f0 + 1:                                   # fail loudly: the .partial stays, its frames kept
            raise RostrumError(codes.RENDER_FAILED, where, f"the frames of {info['id']}", f"are {len(got)} whole frames, expected {f1 - f0 + 1}",
                               hint="Nothing was listed as a version.")
        if say:
            say("Making the MP4")
        _encode(where, pngs, name, f0, fps, mp4, partial)
        share = share_copy(where, mp4, (w, h))
    if keep_exr:
        _renumber(partial, name, "exr", f0, FIRST)
    shutil.rmtree(pngs)
    (partial / resume.RESUME).unlink(missing_ok=True)
    files = [mp4.name, share.name, *(sorted(p.name for p in partial.glob("*.exr")))]
    done = _finish(partial, is_version, _manifest(doc.item_id, doc, info, partial, renderer, (w, h), list(range(f0, f1 + 1)), files, FIRST,
                                                  (out or {}).get("channels")))
    return done, [done / n for n in files], out or {}


def video_job(ctx, args, gate: Gate | None = None):
    """render_video's work as (label, job function, key), checked now (the shot, the range, ffmpeg, output_folder): render_send_shot renders through it."""
    doc, info = doc_and_shot(ctx, args)
    fps, s = info["fps"], render_settings(doc, info)
    renderer = _renderer(args, s)
    f0 = s["start"] if "start" not in args else info["start"] + round(args["start"] * fps)          # default: the shot's render range
    f1 = s["end"] if "end" not in args else info["start"] + round(args["end"] * fps)
    if f0 > f1:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"range {f0}–{f1}", "must run forward")
    check_frame(ctx, info, f0), check_frame(ctx, info, f1)
    check_ffmpeg(ctx.tool)
    target = _out_target(ctx.tool, args)
    w, h = size_of(info, args, s["width"])
    w, h = w - w % 2, h - h % 2                # H.264 needs even sizes
    scene0, doc = draw.scene_of(doc, info["id"]), DocView.of(doc)
    engine, item, count = draw.engine_of(ctx), doc.item_id, f1 - f0 + 1
    keep_exr = args.get("exr", False)
    last_key = render_last.key(ctx.app.folder, item, info["id"])     # a refine is never quietly worse than the last export
    renderer, cycles, same_note = render_last.keep(last_key, renderer, _cycles(args, renderer, s), args)
    passes = layers.chosen(ctx.tool, args, _shot(doc, info), renderer, keep_exr)
    exposure = args.get("exposure", 0)
    said = [same_note] if same_note else []

    def run(job):
        t_start = time.perf_counter()
        scene = ready_for_render(ctx.tool, doc.data, info["id"], ctx.app.folder, scene0)   # its simulation, computed first if needed
        key = video_key(scene0, info, f0, f1, renderer, (w, h), cycles, exposure, keep_exr, passes)
        kept = kept_count(ctx.app.folder, doc, info, key, f0, f1, keep_exr)
        todo, cont = count - kept, resume.continues_text(kept)
        budget_s = args["budget_min"] * 60 if "budget_min" in args else None
        try:
            est, data_est, at = _estimate(ctx, engine, scene, info, renderer, (w, h), (f0, f1), args, s, passes, todo,
                                          must=budget_s is not None or args.get("estimate_only", False), item=item, cycles=cycles)
            note = (f"estimated {est:.0f} s" if est is not None else "not estimated") + (f"; {cont.lower()}" if cont else "")
            over = budget_s is not None and est > budget_s
            fits = estimate.fitting_settings(est, budget_s, renderer, cycles.get("samples", 0), w, at) if over else []
            if over and not args.get("estimate_only"):
                raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"{todo} frames at {w}×{h}, {renderer}", estimate.over_budget_text(est, budget_s, fits),
                                   hint="Nothing was rendered.")
            kept_words = f" {cont} (kept from a stopped or failed render of the same thing)." if cont else ""
            if args.get("estimate_only"):                 # the figures, also over the budget (then with the settings that fit)
                got = Reply(f'Estimate for {info["id"]}: {todo} frames to draw, {w}×{h}, {renderer}: about {est:.0f} s ({est / 60:.1f} min), '
                            f'{data_est["seconds_per_frame"]:.2f} s a frame ({data_est["how"]}).{kept_words} No video was rendered.'
                            + (f" It {estimate.over_budget_text(est, budget_s, fits)}" if over else "") + "".join(f" {w}" for w in said),
                            {"frames": todo, "kept_frames": kept, "renderer": renderer, **data_est, "over_budget": over, "fits": fits},
                            warnings=[*said, *engine.take_notices(), *filter(None, [fall_note(doc.data, info["id"], ctx.app.folder, (f0, f1))]),
                                     *shot_faults(doc.data, info["id"], ctx.app.folder, (f0, f1))])
                if gate:
                    gate.decide(reply=got)
                return got
        except RostrumError as e:                         # a refusal (over the budget, a failed probe): the tool answers with it at once
            if gate:
                gate.decide(error=e)
            raise
        if gate:
            gate.decide()
        job.progress(kept, count, f"frame {kept} of {count}; {note}")
        t_draw = time.perf_counter()
        done, paths, _ = video(ctx.tool, doc, info, scene0, engine, (w, h), renderer, cycles, f0, f1, ctx.app.folder, exposure, keep_exr, passes,
                               progress=lambda i, n: job.progress(i, n, f"frame {i} of {n}; {note}"), stopped=job.cancel_requested.is_set,
                               say=lambda words: job.progress(count, count, words))
        learn_key = estimate_learn.key(ctx.app.folder, item, info["id"], renderer)
        if est is not None and todo > 0:         # what the guess missed, for the next guess of this shot
            estimate_learn.record(learn_key, est / estimate_learn.factor(learn_key), time.perf_counter() - t_draw)
        render_last.remember(last_key, renderer, cycles)
        copies = _copy_out(ctx.tool, paths[0], paths[1], target) if target is not None else []
        took = time.perf_counter() - t_start
        return Reply(f'Rendered {info["id"]}: {count} frames at {fps:g} fps, {w}×{h}, {renderer}, as {paths[0].name} (share copy {paths[1].name}), in {took:.0f} s '
                     f'({took / max(todo, 1):.2f} s a frame drawn; {note}).{kept_words}'
                     + (f" Copied to {copies[0]} and {copies[1].name}." if copies else "") + "".join(f" {w}" for w in said)
                     + " " + next_steps(count, fps, "render_video"),
                     {"frames": count, "kept_frames": kept, "fps": fps, "start_frame": f0, "end_frame": f1, "renderer": renderer, "folder": str(done),
                      **data_est, "seconds": round(took, 1), "seconds_per_frame": round(took / max(todo, 1), 3),
                      **({"copies": [str(c) for c in copies]} if copies else {})},
                     [*paths, *copies], warnings=[*said, *engine.take_notices(), *filter(None, [fall_note(doc.data, info["id"], ctx.app.folder, (f0, f1))]),
                                     *shot_faults(doc.data, info["id"], ctx.app.folder, (f0, f1))])

    def job_fn(job):
        try:
            return run(job)
        except BaseException as e:               # a failure before the estimate was decided: the tool answers with it at once too
            if gate and not gate.decided():
                gate.decide(error=e if isinstance(e, RostrumError) else RostrumError(codes.RENDER_FAILED, ctx.tool, info["id"], f"failed: {e}"))
            raise

    return (f'render_video {info["id"]} f{f0}-{f1}', job_fn, f"video|{item}|{info['id']}|{f0}|{f1}|{renderer}|{w}|{args}|{doc.seq}")


def check_ffmpeg(where: str):
    if shutil.which("ffmpeg") is None:
        raise RostrumError(codes.RENDER_FAILED, where, "the ffmpeg program", "was not found on the PATH; the mp4 is encoded with it",
                           hint="Install FFmpeg (LGPL build) and put it on the PATH, or render pictures instead.")


def _estimate(ctx, engine, scene: dict, info: dict, renderer: str, size: tuple[int, int], frames: tuple[int, int], args: dict, s: dict,
              passes, todo: int, must: bool, item=None, cycles: dict | None = None) -> tuple[float | None, dict, object]:
    """The video's time, measured the way render_estimate measures it (estimate_job: its own engine, the middle frame at a quarter
    and at the real size, kept by scene, so asking again or with other samples answers at once) and scaled by estimate.scale.
    Never by drawing the same frame twice on this engine: the second is answered from the picture it already has (~0.2 s
    for a 3.4 s frame), which made the old estimates 3.5-5x low. `must` (a budget or estimate_only): a failed probe is the
    call's error; otherwise the video is rendered without an estimate. (seconds or None, reply data, at() for fitting_settings)"""
    pe = {**s, "renderer": renderer, "width": size[0], "height": size[1], "start": frames[0], "end": frames[1], "passes": passes,
          **((cycles if cycles is not None else _cycles(args, renderer, s)) if renderer == "cycles" else {"samples": 0})}
    try:
        m = estimate_job.measure(scene, info, pe, ctx.tool, make_engine=lambda: type(engine)(engine.exe, engine._env, engine.args))
    except RostrumError as e:
        if must:
            raise
        return None, {"estimate_s": None, "estimate_error": e.line()}, None
    k = estimate_learn.key(ctx.app.folder, item, info["id"], renderer)
    e = estimate_learn.apply(estimate.scale(m, pe, todo, mp4=True), k)   # only the frames still to draw (kept ones are done)
    how = "a kept measurement of this scene" if m["cached"] else "measured now on this scene"
    if words := estimate_learn.words(e):
        how += f"; {words}"
    if note := estimate_job.card_note(m):
        how += f"; {estimate.busy_words(note)}"
    return e["seconds"], {"estimate_s": e["seconds"], "seconds_per_frame": e["seconds_per_frame"], "how": how,
                          "gpu_busy": estimate_job.card_note(m)}, (lambda c, v: estimate.seconds_at(m, pe, todo, True)(c, v) * e.get("learned", 1.0))


def _encode(where: str, pngs: Path, name: str, first: int, fps: float, mp4: Path, partial: Path):
    part = mp4.with_name(mp4.stem + ".partial.mp4")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", f"{fps:g}", "-start_number", f"{first:04d}", "-i", str(pngs / f"{name}.%04d.png"),
           "-vf", "scale=out_color_matrix=bt709:out_range=tv", "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", str(part)]
    run = subprocess.run(cmd, capture_output=True, text=True)
    if run.returncode != 0 or not part.is_file() or part.stat().st_size == 0:
        raise RostrumError(codes.RENDER_FAILED, where, f"the video {mp4.name}", f"could not be encoded (ffmpeg exit {run.returncode}): {run.stderr.strip()[-400:]}",
                           hint=f"The frames are kept in {pngs}.")
    part.replace(mp4)


SHARE_MBIT_1080 = 8.0                                # the share copy's rate at 1920×1080; other sizes scale by their pixels


def share_copy(where: str, mp4: Path, size: tuple[int, int]) -> Path:
    """A small copy for sharing, `<name>-share.mp4` beside the mp4: H.264 at about 8 Mbit/s for 1920×1080 (scaled by the
    picture's pixels, at least 1 Mbit/s), fast start for the web. Written whole or not at all; a failure is loud."""
    kbit = max(1000, round(SHARE_MBIT_1080 * 1000 * size[0] * size[1] / (1920 * 1080)))
    share = mp4.with_name(mp4.stem + "-share.mp4")
    part = mp4.with_name(mp4.stem + "-share.partial.mp4")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp4), "-c:v", "libx264", "-preset", "medium",
           "-b:v", f"{kbit}k", "-maxrate", f"{kbit * 3 // 2}k", "-bufsize", f"{kbit * 2}k", "-pix_fmt", "yuv420p",
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-movflags", "+faststart", "-an", str(part)]
    run = subprocess.run(cmd, capture_output=True, text=True)
    if run.returncode != 0 or not part.is_file() or part.stat().st_size == 0:
        part.unlink(missing_ok=True)
        raise RostrumError(codes.RENDER_FAILED, where, f"the share copy {share.name}", f"could not be encoded (ffmpeg exit {run.returncode}): {run.stderr.strip()[-400:]}",
                           hint=f"The full video {mp4.name} is made.")
    part.replace(share)
    return share
