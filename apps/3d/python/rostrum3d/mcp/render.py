"""render_still and render_video: pictures for the Editor and the world, always jobs (CONVENTIONS § 7).

A render is a project version `renders/<item>/vNNN/` (the files and a manifest.json, kind "pictures"); a failed one stays in
`vNNN.partial/` and is never listed; a stopped one (cancelled on purpose) leaves nothing (`kept_unless_stopped`). Without a project folder it goes to the render cache. The engine writes each picture to
`<name>.partial` and renames it, so every file is whole; the video is encoded by the `ffmpeg` program (a separate process,
like 2D's) from the PNG frames and written whole or not at all.
"""
from __future__ import annotations

import contextlib
import copy
import re
import shutil
import subprocess
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
from .. import estimate_job
from . import draw, estimate, layers
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


def _folder(folder, doc, info) -> tuple[Path, bool]:
    """A new empty .partial folder: the project's next version, or the render cache. (path, is a project version)"""
    if folder and doc.item_id:
        return project.begin_render(folder, doc.item_id), True
    return render_cache_folder(f'{doc.item_id or "doc"}_{info["id"]}'), False


@contextlib.contextmanager
def kept_unless_stopped(partial: Path, stopped=None):
    """Around a render into `partial`: when it raises because it was stopped on purpose (`stopped()` true: a cancel),
    the half-made folder goes, since nobody wants it; a real failure keeps it (the error names it) to look at."""
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
                                             "budget_min": {"type": "number", "exclusiveMinimum": 0, "description": "Minutes you can spend. The time is measured first (render_estimate's probe, kept for the scene); if the estimate is over this, nothing is rendered and the error names settings that should fit, each with its time."},
                                             "estimate_only": {"type": "boolean", "default": False, "description": "Return the measured estimate (render_estimate's probe of the middle frame, kept for the scene) and render no video."}}})
def render_video(ctx, args):
    """An mp4 (H.264, bt709) of a shot, or of a time range of it, through the shot camera: every frame is rendered (the shot's render Quality by default:
    Cycles, or Stylized when the Quality is Stylized; quality fast = Storm for a draft), then encoded by ffmpeg. A project render with a manifest; `exr` keeps the EXR frames too. Always a
    job: returns a job id at once; ask with inspect_job (wait_s up to 25), which shows 'frames n of m'."""
    return ctx.job(*video_job(ctx, args))


def video_job(ctx, args):
    """render_video's work as (label, job function, key), checked now (the shot, the range, ffmpeg): render_send_shot renders through it."""
    doc, info = doc_and_shot(ctx, args)
    fps, s = info["fps"], render_settings(doc, info)
    renderer = _renderer(args, s)
    f0 = s["start"] if "start" not in args else info["start"] + round(args["start"] * fps)          # default: the shot's render range
    f1 = s["end"] if "end" not in args else info["start"] + round(args["end"] * fps)
    if f0 > f1:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"range {f0}–{f1}", "must run forward")
    check_frame(ctx, info, f0), check_frame(ctx, info, f1)
    if shutil.which("ffmpeg") is None:
        raise RostrumError(codes.RENDER_FAILED, ctx.tool, "the ffmpeg program", "was not found on the PATH; the mp4 is encoded with it",
                           hint="Install FFmpeg (LGPL build) and put it on the PATH, or render_still for single pictures.")
    w, h = size_of(info, args, s["width"])
    w, h = w - w % 2, h - h % 2                # H.264 needs even sizes
    scene0, doc = draw.scene_of(doc, info["id"]), DocView.of(doc)
    engine, item, count = draw.engine_of(ctx), doc.item_id, f1 - f0 + 1
    keep_exr = args.get("exr", False)
    passes = layers.chosen(ctx.tool, args, _shot(doc, info), renderer, keep_exr)

    def job_fn(job):
        t_start = time.perf_counter()
        scene = ready_for_render(ctx.tool, doc.data, info["id"], ctx.app.folder, scene0)   # its simulation, computed first if needed
        budget_s = args["budget_min"] * 60 if "budget_min" in args else None
        est, data_est, at = _estimate(ctx, engine, scene, info, renderer, (w, h), (f0, f1), args, s, passes,
                                  must=budget_s is not None or args.get("estimate_only", False))
        note = f"estimated {est:.0f} s" if est is not None else "not estimated"
        if budget_s is not None and est > budget_s:
            fits = estimate.fitting_settings(est, budget_s, renderer, _cycles(args, renderer, s).get("samples", 0), w, at)
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"{count} frames at {w}×{h}, {renderer}", estimate.over_budget_text(est, budget_s, fits),
                               hint="Nothing was rendered.")
        if args.get("estimate_only"):
            return Reply(f'Estimate for {info["id"]}: {count} frames, {w}×{h}, {renderer}: about {est:.0f} s ({est / 60:.1f} min), '
                         f'{data_est["seconds_per_frame"]:.2f} s a frame ({data_est["how"]}). No video was rendered.',
                         {"frames": count, "renderer": renderer, **data_est}, warnings=engine.take_notices())
        job.progress(0, count, f"frames 0 of {count}; {note}")
        partial, is_version = _folder(ctx.app.folder, doc, info)
        name, mp4 = f'{item or "doc"}_{info["id"]}', partial / f'{item or "doc"}_{info["id"]}.mp4'
        pngs = partial / "_png"
        pngs.mkdir()
        req = {"png": str(pngs / f"{name}.{{frame}}.png"), **({"exr": str(partial / f"{name}.{{frame}}.exr")} if keep_exr else {})}
        with kept_unless_stopped(partial, job.cancel_requested.is_set):     # stopped: no half-made folder left
            out = draw.render(ctx.tool, f"frames {f0}–{f1} of {info['id']}", engine, scene,
                              progress=lambda i, n, _=None: job.progress(i, n, f"frames {i} of {n}; {note}"),
                              camera=info["camera"], renderer=renderer, frames=[f0, f1], width=w, height=h, exposure=args.get("exposure", 0),
                              timeoutS=3600, **req, **_cycles(args, renderer, s), **({"passes": passes} if passes else {}))
            made = sorted(pngs.glob("*.png"))
            if len(made) != count or any(p.stat().st_size == 0 for p in made):        # fail loudly: the .partial stays, nothing is finished
                raise RostrumError(codes.RENDER_FAILED, ctx.tool, f"the frames of {info['id']}", f"are {len(made)} pictures, expected {count}", hint=f"Left in {partial}.")
            _encode(ctx.tool, pngs, name, f0, fps, mp4, partial)
            if keep_exr:
                _renumber(partial, name, "exr", f0, FIRST)
            shutil.rmtree(pngs)
        files = [mp4.name, *(sorted(p.name for p in partial.glob("*.exr")))]
        done = _finish(partial, is_version, _manifest(item, doc, info, partial, renderer, (w, h), list(range(f0, f1 + 1)), files, FIRST,
                                                      out.get("channels")))
        took = time.perf_counter() - t_start
        return Reply(f'Rendered {info["id"]}: {count} frames at {fps:g} fps, {w}×{h}, {renderer}, as {mp4.name}, in {took:.0f} s '
                     f'({took / count:.2f} s a frame; {note}).',
                     {"frames": count, "fps": fps, "start_frame": f0, "end_frame": f1, "renderer": renderer, "folder": str(done), **data_est,
                      "seconds": round(took, 1), "seconds_per_frame": round(took / count, 3)},
                     [done / n for n in files], warnings=engine.take_notices())

    return (f'render_video {info["id"]} f{f0}-{f1}', job_fn, f"video|{item}|{info['id']}|{f0}|{f1}|{renderer}|{w}|{args}|{doc.seq}")


def _estimate(ctx, engine, scene: dict, info: dict, renderer: str, size: tuple[int, int], frames: tuple[int, int], args: dict, s: dict,
              passes, must: bool) -> tuple[float | None, dict, object]:
    """The video's time, measured the way render_estimate measures it (estimate_job: its own engine, the middle frame at a quarter
    and at the real size, kept by scene, so asking again or with other samples answers at once) and scaled by estimate.scale.
    Never by drawing the same frame twice on this engine: the second is answered from the picture it already has (~0.2 s
    for a 3.4 s frame), which made the old estimates 3.5-5x low. `must` (a budget or estimate_only): a failed probe is the
    call's error; otherwise the video is rendered without an estimate. (seconds or None, reply data, at() for fitting_settings)"""
    pe = {**s, "renderer": renderer, "width": size[0], "height": size[1], "start": frames[0], "end": frames[1], "passes": passes,
          **(_cycles(args, renderer, s) if renderer == "cycles" else {"samples": 0})}
    try:
        m = estimate_job.measure(scene, info, pe, ctx.tool, make_engine=lambda: type(engine)(engine.exe, engine._env, engine.args))
    except RostrumError as e:
        if must:
            raise
        return None, {"estimate_s": None, "estimate_error": e.line()}, None
    count = frames[1] - frames[0] + 1
    e = estimate.scale(m, pe, count, mp4=True)
    how = "a kept measurement of this scene" if m["cached"] else "measured now on this scene"
    if note := estimate_job.card_note(m):
        how += f"; {note}"
    return e["seconds"], {"estimate_s": e["seconds"], "seconds_per_frame": e["seconds_per_frame"], "how": how,
                          "gpu_busy": estimate_job.card_note(m)}, estimate.seconds_at(m, pe, count, True)


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
