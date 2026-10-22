"""render_still and render_video: pictures for the Editor and the world, always jobs (CONVENTIONS § 7).

A render is a project version `renders/<item>/vNNN/` (the files and a manifest.json, kind "pictures"); a failed one stays in
`vNNN.partial/` and is never listed. Without a project folder it goes to the render cache. The engine writes each picture to
`<name>.partial` and renames it, so every file is whole; the video is encoded by the `ffmpeg` program (a separate process,
like 2D's) from the PNG frames and written whole or not at all.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from rostrum_core import project
from rostrum_core.storage import doc_hash
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_core.mcp.files import render_cache_folder

from . import draw, estimate
from .shot import ITEM_SHOT, QUALITY, RENDERERS, TIME, check_frame, doc_and_shot, frame_of, renderer_of, seconds, size_of

tools = Tools()
FIRST = 1001                                   # the first frame of every picture hand-off (shared/HANDOFFS.md § 6)
QUALITY_ARG = {"enum": list(QUALITY), "default": "final", "description": "final = Cycles (path traced), fast = Storm (a draft)."}
SETTINGS = {
    "renderer": {"enum": list(RENDERERS), "description": "Overrides quality: storm, cycles or stylized."},
    "width": {"type": "integer", "minimum": 64, "maximum": 8192, "description": "Picture width in px. Default: the shot's own width; the height follows."},
    "samples": {"type": "integer", "minimum": 1, "maximum": 8192, "default": 128, "description": "Cycles samples per pixel."},
    "denoise": {"type": "boolean", "default": True, "description": "Cycles denoising."},
    "exposure": {"type": "number", "default": 0, "description": "Stops, applied to the PNG only (the EXR stays scene-linear)."},
}


def _cycles(args: dict, renderer: str) -> dict:
    return {"samples": args.get("samples", 128), "denoise": args.get("denoise", True)} if renderer == "cycles" else {}


def _manifest(item, doc, info, partial: Path, renderer: str, size, frames: list[int], files: list[str], first_file: int) -> dict:
    fps = info["fps"]
    return {"item": item, "version": int(m.group(1)) if (m := re.match(r"^v(\d+)\.partial$", partial.name)) else 0, "kind": "pictures",
            "made_by": "agent:rostrum-3d", "made_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": {"document": item, "history_entry": doc.seq, "doc_hash": doc_hash(doc.data), "shot": info["id"], "camera": info["camera"]},
            "engine": f"rostrum-3d ({renderer})", "frames": {"first": first_file, "last": first_file + len(frames) - 1, "fps": f"{fps:g}/1",
                                                            "shot_frames": [frames[0], frames[-1]]},
            "size": list(size), "colour": {"space": "scene-linear Rec.709 (EXR), sRGB display (PNG, OpenColorIO)"},
            "files": files, "checks": {"frame_count": "ok", "readable": "ok"}}


def _folder(folder, doc, info) -> tuple[Path, bool]:
    """A new empty .partial folder: the project's next version, or the render cache. (path, is a project version)"""
    if folder and doc.item_id:
        return project.begin_render(folder, doc.item_id), True
    return render_cache_folder(f'{doc.item_id or "doc"}_{info["id"]}'), False


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
          exposure: float = 0, settings: dict | None = None, folder=None) -> tuple[Path, list[Path], dict]:
    """One picture of a shot frame through its camera, as a whole project render version (or in the render cache without a
    project folder). The one code path of the render_still tool and the 3D screen's Render button. Blocking: call it from a job.
    Returns (the finished folder, its files, the engine's reply); a failure raises RENDER_FAILED and leaves only a .partial."""
    partial, is_version = _folder(folder, doc, info)
    item, (w, h) = doc.item_id, size
    name = f'{item or "doc"}_{info["id"]}_f{frame:04d}'
    req = {f: str(partial / f"{name}.{f}") for f in formats}
    out = draw.render(where, f"frame {frame} of {info['id']}", engine, scene, camera=info["camera"], renderer=renderer, frame=frame,
                      width=w, height=h, exposure=exposure, **req, **(settings or {}))
    done = _finish(partial, is_version, _manifest(item, doc, info, partial, renderer, (w, h), [frame], [Path(p).name for p in req.values()], FIRST))
    return done, [done / Path(p).name for p in req.values()], out


@tools.tool("render_still", {"properties": {**ITEM_SHOT, **TIME, "quality": QUALITY_ARG, **SETTINGS,
                                             "formats": {"type": "array", "items": {"enum": ["png", "exr"]}, "minItems": 1, "uniqueItems": True,
                                                         "default": ["png", "exr"], "description": "png = 8-bit sRGB picture, exr = scene-linear half-float for the Editor."}}})
def render_still(ctx, args):
    """One final picture of a shot through the shot camera (Cycles by default), as a project render with a manifest: png (sRGB, through
    OpenColorIO) and/or exr (scene-linear, for the Editor). Always a job: it returns a job id at once; ask with inspect_job (wait_s up to 25)."""
    doc, info = doc_and_shot(ctx, args)
    frame, renderer = frame_of(ctx, info, args), renderer_of(args, "final")
    w, h = size_of(info, args, info["width"])
    formats = args.get("formats", ["png", "exr"])
    scene, engine, item = draw.scene_of(doc, info["id"]), draw.engine_of(ctx), doc.item_id

    def job_fn(job):
        done, files, out = still(ctx.tool, doc, info, scene, engine, frame, renderer, (w, h), formats, args.get("exposure", 0),
                                 _cycles(args, renderer), ctx.app.folder)
        return Reply(f'Rendered frame {frame} ({seconds(info, frame):.3f} s) of {info["id"]}: {w}×{h}, {renderer}, {out["frames"][0]["ms"] / 1000:.1f} s.',
                     {"frame": frame, "time": seconds(info, frame), "renderer": out.get("renderer", renderer), "timing": out.get("timing", {}),
                      "vram": out.get("vram", {}), "folder": str(done)}, files, warnings=engine.take_notices())

    return ctx.job(f'render_still {info["id"]} f{frame}', job_fn, key=f"still|{item}|{info['id']}|{frame}|{renderer}|{w}|{args}|{doc.seq}")


@tools.tool("render_video", {"properties": {**ITEM_SHOT, "quality": QUALITY_ARG, **SETTINGS,
                                             "start": {"type": "number", "minimum": 0, "description": "Seconds from the start of the shot. Default 0."},
                                             "end": {"type": "number", "minimum": 0, "description": "Seconds from the start of the shot (the frame at this time is the last one). Default: the last frame of the shot."},
                                             "exr": {"type": "boolean", "default": False, "description": "Also keep every frame as scene-linear EXR next to the mp4 (what the Editor wants)."},
                                             "budget_min": {"type": "number", "exclusiveMinimum": 0, "description": "Minutes you can spend. One probe frame is timed first; if the estimate is over this, nothing is rendered and the error names settings that should fit."},
                                             "estimate_only": {"type": "boolean", "default": False, "description": "Time one probe frame (the middle one) and return the estimate; render no video."}}})
def render_video(ctx, args):
    """An mp4 (H.264, bt709) of a shot, or of a time range of it, through the shot camera: every frame is rendered (Cycles by default;
    quality fast = Storm for a draft), then encoded by ffmpeg. A project render with a manifest; `exr` keeps the EXR frames too. Always a
    job: returns a job id at once; ask with inspect_job (wait_s up to 25), which shows 'frames n of m'."""
    doc, info = doc_and_shot(ctx, args)
    fps, renderer = info["fps"], renderer_of(args, "final")
    f0 = info["start"] + round(args.get("start", 0.0) * fps)
    f1 = info["end"] if "end" not in args else info["start"] + round(args["end"] * fps)
    if f0 > f1:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"range {f0}–{f1}", "must run forward")
    check_frame(ctx, info, f0), check_frame(ctx, info, f1)
    if shutil.which("ffmpeg") is None:
        raise RostrumError(codes.RENDER_FAILED, ctx.tool, "the ffmpeg program", "was not found on the PATH; the mp4 is encoded with it",
                           hint="Install FFmpeg (LGPL build) and put it on the PATH, or render_still for single pictures.")
    w, h = size_of(info, args, info["width"])
    w, h = w - w % 2, h - h % 2                # H.264 needs even sizes
    scene, engine, item, count = draw.scene_of(doc, info["id"]), draw.engine_of(ctx), doc.item_id, f1 - f0 + 1
    keep_exr = args.get("exr", False)

    def job_fn(job):
        t_start = time.perf_counter()
        probe_ms, probe_note = _probe(ctx.tool, engine, scene, info, (f0 + f1) // 2, renderer, (w, h), args)
        est = estimate.total_seconds(probe_ms, count)
        note = f"estimated {est:.0f} s ({probe_ms:.0f} ms a frame; {probe_note})"
        data_est = {"estimate_s": round(est, 1), "probe_ms": round(probe_ms), "probe_note": probe_note}
        budget_s = args["budget_min"] * 60 if "budget_min" in args else None
        if budget_s is not None and est > budget_s:
            fits = estimate.fitting_settings(est, budget_s, renderer, args.get("samples", 128), w)
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"{count} frames at {w}×{h}, {renderer}", estimate.over_budget_text(est, budget_s, fits),
                               hint="Nothing was rendered.")
        if args.get("estimate_only"):
            return Reply(f'Estimate for {info["id"]}: {count} frames, {w}×{h}, {renderer}: about {est:.0f} s ({est / 60:.1f} min), from one probe frame at '
                         f'{probe_ms:.0f} ms ({probe_note}). No video was rendered.', {"frames": count, "renderer": renderer, **data_est}, warnings=engine.take_notices())
        job.progress(0, count, f"frames 0 of {count}; {note}")
        partial, is_version = _folder(ctx.app.folder, doc, info)
        name, mp4 = f'{item or "doc"}_{info["id"]}', partial / f'{item or "doc"}_{info["id"]}.mp4'
        pngs = partial / "_png"
        pngs.mkdir()
        req = {"png": str(pngs / f"{name}.{{frame}}.png"), **({"exr": str(partial / f"{name}.{{frame}}.exr")} if keep_exr else {})}
        draw.render(ctx.tool, f"frames {f0}–{f1} of {info['id']}", engine, scene, progress=lambda i, n, _=None: job.progress(i, n, f"frames {i} of {n}; {note}"),
                    camera=info["camera"], renderer=renderer, frames=[f0, f1], width=w, height=h, exposure=args.get("exposure", 0),
                    timeoutS=3600, **req, **_cycles(args, renderer))
        made = sorted(pngs.glob("*.png"))
        if len(made) != count or any(p.stat().st_size == 0 for p in made):        # fail loudly: the .partial stays, nothing is finished
            raise RostrumError(codes.RENDER_FAILED, ctx.tool, f"the frames of {info['id']}", f"are {len(made)} pictures, expected {count}", hint=f"Left in {partial}.")
        _encode(ctx.tool, pngs, name, f0, fps, mp4, partial)
        if keep_exr:
            _renumber(partial, name, "exr", f0, FIRST)
        shutil.rmtree(pngs)
        files = [mp4.name, *(sorted(p.name for p in partial.glob("*.exr")))]
        done = _finish(partial, is_version, _manifest(item, doc, info, partial, renderer, (w, h), list(range(f0, f1 + 1)), files, FIRST))
        took = time.perf_counter() - t_start
        return Reply(f'Rendered {info["id"]}: {count} frames at {fps:g} fps, {w}×{h}, {renderer}, as {mp4.name}, in {took:.0f} s '
                     f'({took / count:.2f} s a frame; estimated {est:.0f} s).',
                     {"frames": count, "fps": fps, "start_frame": f0, "end_frame": f1, "renderer": renderer, "folder": str(done), **data_est,
                      "seconds": round(took, 1), "seconds_per_frame": round(took / count, 3)},
                     [done / n for n in files], warnings=engine.take_notices())

    return ctx.job(f'render_video {info["id"]} f{f0}-{f1}', job_fn, key=f"video|{item}|{info['id']}|{f0}|{f1}|{renderer}|{w}|{args}|{doc.seq}")


def _probe(where: str, engine, scene: dict, info: dict, frame: int, renderer: str, size: tuple[int, int], args: dict) -> tuple[float, str]:
    """Time one frame the way the export draws it (same path, size, samples). The engine reports no scene-load or kernel-compile time
    apart from the frame's, so a quick probe is drawn twice and the second is used; a slow one (the first would be as costly as the
    second) is used as it is, and that is said. (ms, how it was measured)"""
    with tempfile.TemporaryDirectory(prefix="rostrum3d_probe_") as tmp:
        def one() -> float:
            r = draw.render(where, f"probe frame {frame} of {info['id']}", engine, scene, camera=info["camera"], renderer=renderer, frame=frame,
                            width=size[0], height=size[1], png=str(Path(tmp) / "probe.png"), exposure=args.get("exposure", 0), **_cycles(args, renderer))
            return float(r["frames"][0]["ms"])
        first = one()
        if first >= estimate.WARM_PROBE_MS:
            return first, "one probe frame, may include scene load, so the estimate can be a little high"
        return one(), "second probe frame, after a warm-up one"


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
