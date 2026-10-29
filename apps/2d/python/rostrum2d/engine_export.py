"""A long export that survives its engine: engine.py `Engine.export` runs here. A video file is drawn in parts of
PART_FRAMES (one engine `export` request each, the encoder writing each part to its own file) and the parts are joined
by FFmpeg without re-encoding (`-c copy`). When the engine dies or gets stuck, it is started again with the scene and
only the part it was on is drawn again: the finished parts are kept. After RESTARTS restarts the export fails loudly,
naming where it stopped. Formats with no single file (picture sequences, GIF) are one request, sent again whole after
a restart. Undertow (2026-10-29): an engine that ended at frame 600 of 900 lost the whole export.

Progress is the whole export's (done, of all frames) with the time so far and an honest time left: the frames still to
draw at the pace of the last PACE_FRAMES (a slow title at the end shows as it comes, not averaged away).
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

PART_FRAMES = 300            # frames per part of a video file (10 s at 30 fps): at most this many are drawn again after a restart
RESTARTS = 2                 # engine restarts one export may take; one more failure fails it
PACE_FRAMES = 30             # the recent frames whose pace gives the time left


def run(eng, req: dict, progress, send) -> dict:
    """`send(req, limit_s, on_line, stuck)`: the engine request, watched (engine.py `_send`), raising EngineError
    subclasses; `on_line(line)` gets each progress line, `stuck(seen)` names where it stopped."""
    from . import engine
    from .engine import EngineError, _Died, Stuck, _log_line
    fps, start = eng._props()["fps"], req.get("start", 0.0)
    end = req.get("end", eng._props()["duration"])
    total = max(1, round((end - start) * fps))
    parts = _parts(req, total)
    pace = _Pace(total, progress)
    done_parts, replies, restarts, tried = [], [], 0, []
    k = 0
    try:
        while k < len(parts):
            a, b, out = parts[k]
            if out:                                 # each try its own file: a dead engine's encoder may still hold the last
                out = _try_name(out, restarts)
                tried.append(out)
            sub = _part_request(req, start, fps, a, b, out) if out else req
            try:
                # A frame that got stuck is given longer after each restart: slow but drawing is not stuck.
                reply = send({"export": {**sub, "progress": True}}, engine.FRAME_LIMIT_S * (1 + restarts),
                             lambda line, a=a: pace.line(a, line), lambda seen, a=a: _stuck(seen, a, total, start, fps))
            except (_Died, Stuck) as e:
                if eng._stopped or restarts >= RESTARTS:
                    raise type(e)(f"{e}{_restarted(restarts)}") from e
                restarts += 1
                _log_line(f"2D export: the engine stopped in frames {a}-{b - 1} ({e}); restarting it ({restarts} of {RESTARTS}) "
                          f"and drawing from frame {a} again, the {a} frames before kept")
                try:
                    eng._restart()
                except EngineError as again:
                    raise type(e)(f"{e}{_restarted(restarts - 1)}; starting it again failed: {again}") from again
                pace.back_to(a)
                continue
            if out and reply.get("frames") != b - a:
                raise EngineError(f"2D export: frames {a}-{b - 1} came back as {reply.get('frames')} frames, not {b - a}")
            replies.append(reply)
            if out:
                done_parts.append(out)
            k += 1
        if len(done_parts) > 1:
            _join(done_parts, req["file"])
        elif done_parts:
            Path(done_parts[0]).replace(req["file"])
    finally:                                        # the parts never outlive the export (done: joined; failed: the export leaves nothing)
        for p in tried:
            try:
                Path(p).unlink(missing_ok=True)
            except OSError:                         # still held by a dead engine's encoder: one log line, never a failed export
                _log_line(f"2D export: could not remove the part {p}")
    out = _merged(replies, total if len(replies) > 1 else None)
    if restarts:
        out["restarts"] = restarts
        out["warning"] = " ".join(w for w in (out.get("warning"), f"The engine stopped {restarts} time(s) and was restarted; "
                                              "the frames already drawn were kept.") if w)
    return out


def _try_name(part: str, n: int) -> str:
    p = Path(part)
    return part if not n else str(p.with_name(f"{p.stem}.try{n}{p.suffix}"))


def _stuck(seen: dict | None, offset: int, total: int, start: float, fps: float) -> str:
    """Words naming where an export stopped: `seen` the part's last progress line, `offset` the part's first frame."""
    done = offset + (seen["progress"] if seen else 0)
    at = round(start * fps) + done
    if not done:
        return f"drew no frame of the export, not even its first (frame {at}, {start:.2f} s)"
    return f"drew nothing after {done} of {total} frames: stuck at frame {at} ({at / fps:.2f} s) or one just after"


def _restarted(n: int) -> str:
    return f" (after {n} restart{'s' if n != 1 else ''} of the engine)" if n else ""


def _parts(req: dict, total: int) -> list[tuple[int, int, str | None]]:
    """[(first frame, end frame, the part's file or None for the request as it is)]. A video file is split when it is
    longer than a part and its encoder names the file once (so each part can name its own)."""
    file = req.get("file")
    args = (req.get("encode") or {}).get("args") or []
    if not file or total <= PART_FRAMES or args.count(file) != 1:
        return [(0, total, None)]
    p = Path(file)
    return [(a, min(a + PART_FRAMES, total), str(p.with_name(f"{p.stem}.part{a // PART_FRAMES:03d}{p.suffix}")))
            for a in range(0, total, PART_FRAMES)]


def _part_request(req: dict, start: float, fps: float, a: int, b: int, out: str) -> dict:
    enc = req["encode"]
    args = [out if x == req["file"] else x for x in enc["args"]]
    sub = {**req, "start": start + a / fps, "end": start + b / fps, "file": out, "encode": {**enc, "args": args}}
    if a:                                           # the engine's timing table: the first part's (it is per request)
        sub.pop("timingCsv", None)
    return sub


def _join(parts: list[str], file: str) -> None:
    """The parts joined in order into `file` without re-encoding (FFmpeg's concat), then removed."""
    from . import settings
    target = Path(file)
    listing = target.with_name(target.stem + ".parts.txt")
    listing.write_text("".join(f"file '{Path(p).as_posix()}'\n" for p in parts), encoding="utf-8")
    try:
        run_ = subprocess.run([settings.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
                               "-i", str(listing), "-c", "copy", str(target)], capture_output=True, text=True,
                              creationflags=settings.NO_WINDOW)
        if run_.returncode or not target.is_file():
            raise RuntimeError(f"joining the export's {len(parts)} parts into {target.name} failed "
                               f"(ffmpeg exit {run_.returncode}): {run_.stderr.strip()[-400:]}")
    finally:
        listing.unlink(missing_ok=True)
    for p in parts:
        Path(p).unlink(missing_ok=True)


def _merged(replies: list[dict], total: int | None) -> dict:
    """One reply for the parts: the last part's, with frames counted over all and the timing's seconds added up."""
    out = dict(replies[-1])
    if total is None:
        return out
    out["frames"] = sum(r.get("frames", 0) for r in replies)
    timing = {}
    for r in replies:
        for key, v in (r.get("timing") or {}).items():
            if isinstance(v, (int, float)) and key.endswith("S"):
                timing[key] = timing.get(key, 0) + v
            elif key == "maxMs":
                timing[key] = max(timing.get(key, 0), v)
            else:
                timing.setdefault(key, v)
    out["timing"] = timing
    return out


class _Pace:
    """The whole export's progress line from each part's: done over all frames, the time since it began, and the time
    left at the pace of the last PACE_FRAMES frames drawn."""

    def __init__(self, total: int, progress):
        self.total, self.progress, self.t0 = total, progress, time.perf_counter()
        self.times: list[float] = []         # when each frame of the export so far came

    def back_to(self, done: int):
        del self.times[done:]

    def line(self, offset: int, line: dict) -> dict:
        done = offset + line["progress"]
        now = time.perf_counter()
        del self.times[done:]
        self.times.extend([now] * (done - len(self.times)))
        recent = self.times[-PACE_FRAMES - 1:]
        per = (recent[-1] - recent[0]) / (len(recent) - 1) if len(recent) > 1 else now - self.t0
        out = {"progress": done, "of": self.total, "elapsedS": now - self.t0, "leftS": per * (self.total - done)}
        if self.progress:
            from .engine import _progress
            _progress(self.progress, out)
        return out
