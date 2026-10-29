"""An MP4 export drawn in segments (export_segments.py), each kept by its key in the cache (CACHE, capped at CAP_GB,
the longest unused removed first): a re-export draws only the segments whose key changed and joins all of them with
FFmpeg's concat, without re-encoding (`-c copy`). Each run of neighbouring segments to draw is one engine request
carrying its parts' ends and files (the engine's `saves`, a part = up to 10 s of whole segments): its held encoder
finishes each part's file at its end while the frames after it are drawn, and each part is cut into its segments
(FFmpeg, no re-encoding), so a stop or a crash keeps every finished part and the next export draws only the rest (engine_export.py goes on from the first one missing after a restart). One engine draws: an export
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
            for run in _runs(todo):
                a, b = cuts[run[0]][0], cuts[run[-1]][1]
                parts = _parts(run, cuts)
                saves = [(cuts[p[-1]][1] - a, home / f"part{cuts[p[0]][0]}.{os.getpid()}.partial.mp4") for p in parts]
                try:
                    got = _draw(io_export, eng, s, start, fps, a, b, saves, _part_progress(progress, drawn, to_draw))
                finally:                             # every part saved whole, also when the request failed, into its segments
                    for p, (_, f) in zip(parts, saves):
                        if f.is_file():
                            try:
                                _place(f, [cuts[i][0] - cuts[p[0]][0] for i in p[1:]], [files[i] for i in p])
                            finally:
                                f.unlink(missing_ok=True)
                facts = {**got, **facts}
                drawn += b - a
    for f in files:                                  # used now: the last removed when the cache is over its cap
        os.utime(f)
    _join(files, target)
    # Read back without decoding: the engine checked each segment's frame count as its encoder saved it and the join
    # only copies their packets, so counting the packets (one a frame) and reading the size proves the film whole.
    facts = {**facts, "checked": readback.check("mp4", target, total, w, h, False), "alpha": False, "depth": 8}
    facts.update(file=str(target), frames=total, fps=fps)
    took = time.perf_counter() - t0
    facts["segments"] = {"count": len(cuts), "drawn": len(todo), "drawn_s": round(to_draw / fps, 2),
                         "reused": len(cuts) - len(todo), "took_s": round(took, 1)}
    facts["timing"] = {**(facts.get("timing") or {}), "totalS": took}      # the whole export's, as Engine.video says it
    trim()
    return facts


def _runs(todo: list[int]) -> list[list[int]]:
    """The segments to draw, in runs of neighbours: each run one engine request (its frames follow on). Only a re-export
    with changes in several places sends more than one."""
    runs: list[list[int]] = []
    for i in todo:
        if runs and runs[-1][-1] == i - 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    return runs


def _parts(run: list[int], cuts) -> list[list[int]]:
    """A run's segments in parts of at most engine_export.PART_FRAMES (whole segments): the engine's encoder saves a file
    at each part's end and Python cuts it into its segments. A file per 2 s segment made the encoder switch writers 33
    times a film: 73 against 147 frames a second, and with two writers made ahead the encoder process died (member B's
    bench, 2026-10-29). A stop or crash keeps every part saved before it."""
    from rostrum2d.engine_export import PART_FRAMES
    parts: list[list[int]] = []
    for i in run:
        if parts and cuts[i][1] - cuts[parts[-1][0]][0] <= PART_FRAMES:
            parts[-1].append(i)
        else:
            parts.append([i])
    return parts


def _place(part: Path, cuts: list[int], into: list[Path]) -> None:
    """A saved part into its segments' files (`cuts`: where each after the first starts, in the part's frames)."""
    if not cuts:
        part.replace(into[0])
    elif not _split(part, cuts, into):
        raise RuntimeError(f"{part.name}: the encoder did not start a picture group at every segment cut {cuts}")


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


def _draw(io_export, eng, s: dict, start: float, fps, a: int, b: int, saves: list[tuple[int, Path]], progress) -> dict:
    """Frames a..b of the export, saved by the engine as `saves` [(end frame counted from a, file)] as it draws: each file
    in place once whole, so a failure keeps the ones finished and never a half one. Checked to hold b - a frames."""
    got = io_export.export(eng, "mp4", saves[-1][1], False, 8, start + a / fps, start + b / fps, progress,
                           s.get("quality"), s.get("bitrate"), saves=saves)
    if got["frames"] != b - a:
        raise RuntimeError(f"frames {a}-{b - 1} came back as {got['frames']} frames, not {b - a}")
    return got


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
    """The segments, in order, into `target` without re-encoding, the index moved to the front (+faststart: a web player
    starts before the whole file is in; ~5-30 ms on a 30 MB film). One file too, so every MP4 has it."""
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
