"""look_frame (what: empty): where a piece is blank, pale or standing still, from small pictures sampled every half second
(a composition drawn by the engine, or a finished mp4). Facts with times and numbers, never a verdict on taste: the agent
decides what is meant to be quiet and looks at the stretch with look_frame."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from .. import settings
from . import render
from .pick import ITEM_COMP, doc_and_comp

tools = Tools()
SAMPLE_W, SAMPLE_H = 160, 90          # the check reads tiny pictures: seconds for a minute of film
EVERY = 0.5
EMPTY_BELOW = 0.03                    # share of the frame that differs from its own background
PALE_FROM, FLAT_BELOW = 0.70, 0.25    # washed out: even the darkest 5 % of pixels this light, and the p5..p95 lightness spread this small
STILL_BELOW = 0.001                   # share of pixels that changed since the sample before
MAX_SAMPLES = 600


def sample_facts(img: np.ndarray) -> dict:
    """What one small picture (h, w, 3 floats 0..1) shows: how much differs from its own background, its lightness range."""
    flat = img.reshape(-1, 3)
    bins = (np.minimum(flat * 8, 7.999).astype(np.int32) * np.array([64, 8, 1])).sum(1)
    mode = np.bincount(bins, minlength=512).argmax()
    bg = flat[bins == mode].mean(0)
    differs = float((np.abs(flat - bg).max(1) > 0.06).mean())
    lum = flat @ np.array([0.2126, 0.7152, 0.0722])
    p5, p95 = np.percentile(lum, [5, 95])
    return {"differs": differs, "p5": float(p5), "spread": float(p95 - p5)}


def analyse(samples: list[tuple[float, np.ndarray]], every: float = EVERY, end: float | None = None, min_still: float = 2.0) -> list[dict]:
    """Stretches worth a look, in time order: {kind, start, end, text, numbers…}. `samples`: (time, picture) in time order."""
    if not samples:
        return []
    last_end = end if end is not None else samples[-1][0] + every
    facts = [sample_facts(img) for _, img in samples]
    for i, (f, (_, img)) in enumerate(zip(facts, samples)):
        f["changed"] = float((np.abs(img - samples[i - 1][1]).max(2) > 0.02).mean()) if i else 1.0
    flags = {"empty": [f["differs"] < EMPTY_BELOW for f in facts],
             "washed": [f["differs"] >= EMPTY_BELOW and f["p5"] >= PALE_FROM and f["spread"] < FLAT_BELOW for f in facts],
             "still": [i > 0 and f["changed"] < STILL_BELOW for i, f in enumerate(facts)]}
    out = []
    for kind, flag in flags.items():
        for a, b in _runs(flag):
            t0, t1 = samples[a][0] - (every if kind == "still" else 0), min(samples[b][0] + every, last_end)
            if kind == "still" and (t1 - t0 < min_still or all(flags["empty"][a:b + 1])):
                continue          # a short pause is not dead air; a blank stretch is named as blank
            run = facts[a:b + 1]
            row = {"kind": kind, "start": round(max(t0, 0.0), 3), "end": round(t1, 3), "ending": b == len(samples) - 1}
            if kind == "empty":
                row["differs_pct"] = round(100 * max(f["differs"] for f in run), 1)
            elif kind == "washed":
                row["lightest_dark_pct"], row["spread_pct"] = round(100 * min(f["p5"] for f in run)), round(100 * max(f["spread"] for f in run))
            else:
                row["changed_pct"] = round(100 * max(f["changed"] for f in run[1:] or run), 2)
            row["text"] = _words(row)
            out.append(row)
    return sorted(out, key=lambda r: (r["start"], r["kind"]))


def _runs(flag: list[bool]):
    start = None
    for i, on in enumerate(flag + [False]):
        if on and start is None:
            start = i
        elif not on and start is not None:
            yield start, i - 1
            start = None


def _words(r: dict) -> str:
    span = f'{r["start"]:g}–{r["end"]:g} s'
    if r["kind"] == "empty":
        return f'{span}: near-empty, at most {r["differs_pct"]:g} % of the frame differs from its background' + (" (the last frame: the ending)" if r["ending"] else "")
    if r["kind"] == "washed":
        return f'{span}: washed out, even the darkest part is {r["lightest_dark_pct"]} % light and the light range is only {r["spread_pct"]} %' + (" (the ending)" if r["ending"] else "")
    return f'{span}: unchanged, at most {r["changed_pct"]:g} % of pixels move between samples' + (" (up to the end)" if r["ending"] else "")


def scan_pngs(items: list[tuple[float, Path]], every: float, end: float, min_still: float = 2.0) -> list[dict]:
    from PIL import Image
    samples = []
    for t, png in items:
        with Image.open(png) as im:
            samples.append((t, np.asarray(im.convert("RGB"), np.float32) / 255))
    return analyse(samples, every, end, min_still)


def scan_video(mp4: Path, start: float = 0.0, every: float = EVERY, min_still: float = 2.0) -> list[dict]:
    """The same check on a finished mp4 (times from `start`, the film's own start on the composition's clock)."""
    cmd = [settings.ffmpeg(), "-hide_banner", "-loglevel", "error", "-i", str(mp4), "-vf", f"fps={1 / every:g},scale={SAMPLE_W}:{SAMPLE_H}",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    run = subprocess.run(cmd, capture_output=True, timeout=300)
    if run.returncode:
        raise RostrumError(codes.RENDER_FAILED, "look_frame (what: empty)", str(mp4), f"ffmpeg could not read it (exit {run.returncode}): {run.stderr.decode(errors='replace')[-200:]}")
    size = SAMPLE_W * SAMPLE_H * 3
    frames = np.frombuffer(run.stdout, np.uint8)[: len(run.stdout) // size * size].reshape(-1, SAMPLE_H, SAMPLE_W, 3).astype(np.float32) / 255
    rows = analyse([(start + i * every, f) for i, f in enumerate(frames)], every, start + len(frames) * every, min_still)
    return rows


def tell(rows: list[dict], start: float, end: float, every: float = EVERY) -> str:
    """The short sentence for a reply: the stretches with their numbers, or that none was found."""
    if not rows:
        return f"No empty, washed-out or unchanged stretch in {start:g}–{end:g} s (sampled every {every:g} s)."
    shown = "; ".join(r["text"] for r in rows[:8]) + (f"; and {len(rows) - 8} more (see data)" if len(rows) > 8 else "")
    return f"Stretches to look at (sampled every {every:g} s): {shown}. Meant to be quiet? Then leave it; else look_frame at those times."


@tools.tool("look_empty", {"properties": {**ITEM_COMP,
                                          "start": {"type": "number", "minimum": 0, "description": "Seconds. Default 0."},
                                          "end": {"type": "number", "minimum": 0, "description": "Seconds. Default: the end of the composition."},
                                          "every": {"type": "number", "minimum": 0.1, "maximum": 5, "default": EVERY, "description": "Seconds between samples. Default 0.5."},
                                          "min_still": {"type": "number", "minimum": 0.5, "default": 2.0, "description": "Seconds nothing moves before it is named. Default 2."},
                                          "video": {"type": "string", "description": "An mp4 to check instead of drawing the composition (absolute path); times then count from `start`."}}})
def look_empty(ctx, args):
    """Find blank, pale and standing-still stretches: samples tiny pictures every `every` seconds (seconds to run) and names, with
    times and numbers, the stretches that are near-empty (almost nothing but background), washed out (everything pale, low contrast),
    or unchanged for `min_still` seconds or more, and whether the film ends on one. Facts, not verdicts: a held title or a planned
    quiet beat is yours to judge; look at a named time with look_frame. render_video runs this on every export."""
    every, start = args.get("every", EVERY), args.get("start", 0.0)
    if "video" in args:
        mp4 = Path(args["video"])
        if not mp4.is_file():
            raise RostrumError(codes.NOT_FOUND, ctx.tool, f'video "{mp4}"', "is not a file", hint="Give the absolute path of an mp4.")
        rows = scan_video(mp4, start, every, args.get("min_still", 2.0))
        end = max([r["end"] for r in rows] + [start])
        return Reply(tell(rows, start, end, every), {"stretches": rows, "video": str(mp4)})
    doc, comp = doc_and_comp(ctx, args)
    fps, duration = comp.get("fps", 30), comp.get("duration", 5.0)
    end = args.get("end", duration)
    if not 0 <= start < end <= duration + 1e-9:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f"range {start}–{end} s", f"must satisfy 0 <= start < end <= {duration:g} (the composition's length)")
    every = max(every, (end - start) / MAX_SAMPLES)
    last = (round(duration * fps) - 1) / fps
    times = [min(start + i * every, last) for i in range(int((end - start) / every + 1e-9))]
    scene = render.scene_of(doc, comp["id"], (times[0], times[-1]), sorted({round(t * fps) for t in times}))

    def job_fn(job):
        with tempfile.TemporaryDirectory(prefix="rostrum_empty_") as tmp:
            items = [(t, Path(tmp) / f"s{i}.png") for i, t in enumerate(times)]
            render.small_stills(ctx.tool, scene, items, SAMPLE_W, job.progress)
            rows = scan_pngs(items, every, end, args.get("min_still", 2.0))
        return Reply(tell(rows, start, end, every), {"stretches": rows, "every": every, "samples": len(times)}, warnings=scene.get("warnings", []))

    return ctx.long(f'look_frame (what: empty) {comp["id"]}', job_fn)
