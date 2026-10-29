"""An MP4 export drawn in segments (export_segments.py), each kept by its key in the cache (CACHE, capped at CAP_GB,
the longest unused removed first): a re-export draws only the segments whose key changed and joins all of them with
FFmpeg's concat, without re-encoding (`-c copy`, as engine_export.py joins its parts). One engine draws: an export
already keeps the processor and graphics card busy with its own workers (engine export_workers.rs), and a second
engine would double the card memory on a 4 GB card. A failed segment fails the export; nothing under the final name.
"""
from __future__ import annotations

import importlib
import os
import subprocess
import time
from pathlib import Path

from rostrum2d import settings

from . import export_segments as segs

CACHE = "2d-export-segments"
CAP_GB = 4.0


def folder() -> Path:
    return settings.cache_dir(CACHE)


def export(scene: dict, s: dict, target: Path, progress, engine_factory, on_stop=None) -> dict:
    """Draw (or reuse) every segment of `scene` from s["start"] to s["end"] and join them into `target`. The facts
    of io/export.py's export, plus `segments`: {count, drawn, drawn_s, reused, took_s}."""
    from rostrum2d.io import formats, readback
    io_export = importlib.import_module("rostrum2d.io.export")    # its export at call time (a test stands in for it)
    t0 = time.perf_counter()
    p = scene["comp"]["props"]
    w, h, fps, start, end = p["width"], p["height"], p["fps"], s["start"], s["end"]
    rate = formats.rate(formats.get("mp4"), w, h, fps, s.get("quality"), s.get("bitrate"))
    encode = {"w": w, "h": h, "fps": fps, "kbps": rate.kbps, "quality": rate.quality}
    cuts = segs.plan(scene, start, end)
    keys = segs.keys(scene, cuts, start, encode)
    home = folder()
    home.mkdir(parents=True, exist_ok=True)
    files = [home / f"{k}.mp4" for k in keys]
    todo = [i for i, f in enumerate(files) if not f.is_file()]
    total = max(1, round((end - start) * fps))
    to_draw = sum(cuts[i][1] - cuts[i][0] for i in todo)
    facts, drawn = {}, 0
    if todo:
        with engine_factory() as eng:
            if on_stop:                              # run_stop ends the engine at once, even mid-frame
                on_stop(eng.kill)
            eng.load(scene)
            for run in _runs(todo, cuts):
                a, b = cuts[run[0]][0], cuts[run[-1]][1]
                got = _draw(io_export, eng, s, start, fps, a, b, home / f"run{a}.{os.getpid()}.partial.mp4",
                            _part_progress(progress, drawn, to_draw))
                facts = {**got, **facts}
                try:
                    if len(run) == 1:
                        Path(got["file"]).replace(files[run[0]])
                    elif not _split(Path(got["file"]), [cuts[i][0] - a for i in run[1:]], [files[i] for i in run]):
                        for i in run:                # the encoder did not start a picture group at each cut: one request each
                            one = _draw(io_export, eng, s, start, fps, *cuts[i], home / f"one{cuts[i][0]}.{os.getpid()}.partial.mp4", None)
                            Path(one["file"]).replace(files[i])
                finally:
                    Path(got["file"]).unlink(missing_ok=True)
                drawn += b - a
    for f in files:                                  # used now: the last removed when the cache is over its cap
        os.utime(f)
    _join(files, target)
    if len(files) > 1 or not todo:                   # the joined file read back whole (one drawn segment was read already)
        facts = {**facts, **_readback(readback, target, total, w, h, fps)}
    facts.update(file=str(target), frames=total, fps=fps)
    took = time.perf_counter() - t0
    facts["segments"] = {"count": len(cuts), "drawn": len(todo), "drawn_s": round(to_draw / fps, 2),
                         "reused": len(cuts) - len(todo), "took_s": round(took, 1)}
    facts["timing"] = {**(facts.get("timing") or {}), "totalS": took}      # the whole export's, as Engine.video says it
    trim()
    return facts


def _runs(todo: list[int], cuts) -> list[list[int]]:
    """The segments to draw, in runs of neighbours drawn by one engine request, each at most engine_export.PART_FRAMES
    long (the engine's own parts: a longer request is split by it at frames that need not be segment cuts)."""
    from rostrum2d.engine_export import PART_FRAMES
    runs: list[list[int]] = []
    for i in todo:
        r = runs[-1] if runs else None
        if r and r[-1] == i - 1 and cuts[i][1] - cuts[r[0]][0] <= PART_FRAMES:
            r.append(i)
        else:
            runs.append([i])
    return runs


def _draw(io_export, eng, s: dict, start: float, fps, a: int, b: int, part: Path, progress) -> dict:
    """Frames a..b of the export into `part`, checked to hold b - a frames; a failure leaves no `part`."""
    part.unlink(missing_ok=True)
    try:
        got = io_export.export(eng, "mp4", part, False, 8, start + a / fps, start + b / fps, progress, s.get("quality"), s.get("bitrate"))
        if got["frames"] != b - a:
            raise RuntimeError(f"frames {a}-{b - 1} came back as {got['frames']} frames, not {b - a}")
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    return {**got, "file": str(part)}


def _split(run: Path, cuts: list[int], into: list[Path]) -> bool:
    """`run` cut at frames `cuts` (each a key picture) into the files `into`, without re-encoding. False (nothing
    written) when a cut is not a key picture."""
    probe = subprocess.run([settings.ffmpeg("ffprobe"), "-v", "error", "-select_streams", "v", "-show_entries", "packet=flags",
                            "-of", "csv=p=0", str(run)], capture_output=True, text=True, creationflags=settings.NO_WINDOW)
    keys = {i for i, f in enumerate(probe.stdout.split()) if f.startswith("K")}
    if probe.returncode or not set(cuts) <= keys:
        return False
    stem = run.with_suffix("").name
    pattern = run.with_name(f"{stem}.%03d.mp4")
    got = subprocess.run([settings.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(run), "-c", "copy", "-f", "segment",
                          "-segment_frames", ",".join(map(str, cuts)), "-reset_timestamps", "1", str(pattern)],
                         capture_output=True, text=True, creationflags=settings.NO_WINDOW)
    pieces = [run.with_name(f"{stem}.{k:03d}.mp4") for k in range(len(into))]
    try:
        if got.returncode or not all(p.is_file() for p in pieces):
            raise RuntimeError(f"splitting {run.name} into {len(into)} segments failed (ffmpeg exit {got.returncode}): {got.stderr.strip()[-400:]}")
        for p, f in zip(pieces, into):
            p.replace(f)
    finally:
        for p in pieces:
            p.unlink(missing_ok=True)
    return True


def _readback(readback, target: Path, total: int, w: int, h: int, fps) -> dict:
    return {"file": str(target), "frames": total, "fps": fps, "alpha": False, "depth": 8,
            "checked": readback.check("mp4", target, total, w, h, False, 8)}


def _part_progress(progress, before: int, of: int):
    """A segment's progress as the export's: frames drawn over all the frames to draw."""
    if progress is None:
        return None

    def step(done, total, note=""):
        try:
            return progress(before + done, of, note) if note else progress(before + done, of)
        except TypeError:                            # a caller that takes (done, total) only
            return progress(before + done, of)
    return step


def _join(files: list[Path], target: Path) -> None:
    """The segments, in order, into `target` (a copy for one), without re-encoding."""
    import shutil
    if len(files) == 1:
        shutil.copyfile(files[0], target)
        return
    listing = target.with_name(target.stem + ".segments.txt")
    listing.write_text("".join(f"file '{f.as_posix()}'\n" for f in files), encoding="utf-8")
    try:
        run = subprocess.run([settings.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                              "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(target)],
                             capture_output=True, text=True, creationflags=settings.NO_WINDOW)
        if run.returncode or not target.is_file():
            raise RuntimeError(f"joining the {len(files)} segments into {target.name} failed (ffmpeg exit {run.returncode}): "
                               f"{run.stderr.strip()[-400:]}")
    finally:
        listing.unlink(missing_ok=True)


def trim(cap_gb: float = CAP_GB) -> None:
    """Remove the longest-unused segments until the cache is under `cap_gb`."""
    try:
        got = [(f.stat().st_mtime, f.stat().st_size, f) for f in folder().glob("*.mp4")
               if ".partial" not in f.name]                # never a segment being drawn
    except OSError:
        return
    size = sum(n for _, n, _ in got)
    for _, n, f in sorted(got):
        if size <= cap_gb * 2**30:
            break
        try:
            f.unlink()
            size -= n
        except OSError:
            pass
