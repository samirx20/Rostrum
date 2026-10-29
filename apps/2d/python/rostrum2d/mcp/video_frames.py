"""Single pictures out of a finished mp4, for look_frame's contact sheets (`video`): the film is read as it is, not redrawn."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from rostrum_core.errors import RostrumError, codes

from .. import settings

_DURATION = re.compile(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)")
_FPS = re.compile(r"(\d+(?:\.\d+)?) fps")


def probe(mp4: Path, where: str) -> tuple[float, float]:
    """(seconds, frames per second) of the film, read from ffmpeg's own description of it."""
    run = subprocess.run([settings.ffmpeg(), "-hide_banner", "-i", str(mp4)], capture_output=True, timeout=60)
    text = run.stderr.decode(errors="replace")
    d, f = _DURATION.search(text), _FPS.search(text)
    if not (d and f):
        raise RostrumError(codes.RENDER_FAILED, where, str(mp4), "is not a film ffmpeg can read (no duration or frame rate found)", hint="Give the absolute path of an mp4.")
    h, m, s = d.groups()
    return int(h) * 3600 + int(m) * 60 + float(s), float(f.group(1))


VIDEO = {"video": {"type": "string", "description": "A finished mp4 to look at instead of drawing the composition (absolute path, e.g. render_export's `video`): with `times`, or what \"sheet\" "
                                                    "with start / end / count (seconds in the film). The pictures are the file's own frames: for checking a file you delivered. While you work, leave it out: "
                                                    "a look at the composition is the same picture without an export, back in well under a second."}}


def video_sheet(ctx, args: dict, times: list[float] | None):
    """The contact sheet of a finished mp4: `times` (seconds in the film), or `count` frames evenly from start to end."""
    from rostrum_core.mcp import Reply, sheet
    from rostrum_core.mcp.files import look_path
    import tempfile
    mp4 = Path(args["video"])
    if not mp4.is_file():
        raise RostrumError(codes.NOT_FOUND, ctx.tool, f'video "{mp4}"', "is not a file", hint="Give the absolute path of an mp4 (render_export's `video`).")
    duration, fps = probe(mp4, ctx.tool)
    last = max(duration - 2 / fps, 0.0)       # ffmpeg seeks to a time at or before the last frame; the very last may give none
    if times is None:
        start, end, count = args.get("start", 0.0), args.get("end", last), args.get("count", 8)
        if not 0 <= start < end <= duration + 1e-9:
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"range {start}–{end} s", f"must satisfy 0 <= start < end <= {duration:.3f} (the film's length)")
        times = [start + (min(end, last) - start) * i / (count - 1) for i in range(count)]
    for t in times:
        if not 0 <= t <= duration + 1e-9:
            raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"time {t} s", f"is outside the film (0 to {duration:.3f} s)")
    times = sorted({round(min(t, last), 3) for t in times})
    cols = min(args.get("cols", 4), len(times))
    tile_w = sheet.tile_width(args.get("width", 1600), cols)
    dest = look_path(f"{mp4.stem}_video_sheet", project=ctx.app.folder)

    def job_fn(job):
        with tempfile.TemporaryDirectory(prefix="rostrum_vsheet_") as tmp:
            tiles = []
            for i, t in enumerate(times):
                png = Path(tmp) / f"v{i}.png"
                picture(mp4, t, png, tile_w, ctx.tool)
                tiles.append((png, f"{t:.2f} s"))
            w, h = sheet.contact_sheet(tiles, tile_w, cols, dest)
        return Reply(f"Contact sheet of the film {mp4.name}: {len(times)} frames from {times[0]:.2f} to {times[-1]:.2f} s ({duration:.2f} s long), {w}×{h}.",
                     {"video": str(mp4), "times": times, "duration": round(duration, 3), "width": w, "height": h, "cols": cols}, [dest], [dest])
    return ctx.long(f"look_frame (what: sheet) {mp4.name}", job_fn)


def picture(mp4: Path, t: float, dest: Path, width: int, where: str) -> None:
    """The frame at `t` seconds, `width` px wide, as a PNG."""
    run = subprocess.run([settings.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.4f}", "-i", str(mp4), "-frames:v", "1",
                          "-vf", f"scale={width}:-2", str(dest)], capture_output=True, timeout=120)
    if run.returncode or not dest.is_file():
        raise RostrumError(codes.RENDER_FAILED, where, f"{mp4.name} at {t:g} s", f"ffmpeg could not read the picture (exit {run.returncode}): {run.stderr.decode(errors='replace')[-200:]}")
