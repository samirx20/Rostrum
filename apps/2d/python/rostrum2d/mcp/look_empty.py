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
from . import edge_cut, render
from .pick import ITEM_COMP, doc_and_comp

tools = Tools()
SAMPLE_W, SAMPLE_H = 160, 90          # the check reads tiny pictures: seconds for a minute of film
EVERY = 0.5
EMPTY_BELOW = 0.03                    # share of the frame that differs from its own background
PALE_FROM, FLAT_BELOW = 0.70, 0.25    # washed out: even the darkest 5 % of pixels this light, and the p5..p95 lightness spread this small
STILL_BELOW = 0.001                   # share of pixels that changed since the sample before
TILE = 5                              # px of the small picture per tile of the plain-block check (32 x 18 tiles)
PLAIN_WITHIN = 0.035                  # a tile is plain when every pixel is this close to its mean (each channel, 0..1)
BLOCK_FROM = 0.06                     # a plain block: one colour over at least this share of the frame, not the background
BLOCK_SAME = 0.03                      # ... every tile of it this close to the first one (a soft glow or gradient is no block)
BLOCK_FULL = 0.8                      # ... that fills this much of its own box (a card, not a floor with things in front of it)
BLOCK_CHANGED = 0.15                  # ... and whose box changed this much (share of itself) against a sample beside it
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


def plain_blocks(img: np.ndarray, bg: np.ndarray) -> list[dict]:
    """Big one-colour boxes of a small picture that are not its background: connected plain tiles of one colour that
    fill most of their own box and touch at most one edge of the frame (not a floor, a sky or a band of background
    between things), as {share of the frame, colour, box (x, y, w, h) 0..1}. A card with nothing on it shows here; a card with text,
    an icon or an edge through it breaks into smaller pieces."""
    h, w = img.shape[0] // TILE, img.shape[1] // TILE
    tiles = img[: h * TILE, : w * TILE].reshape(h, TILE, w, TILE, 3).transpose(0, 2, 1, 3, 4).reshape(h, w, TILE * TILE, 3)
    mean = tiles.mean(2)
    plain = (np.abs(tiles - mean[:, :, None, :]).max((2, 3)) < PLAIN_WITHIN) & (np.abs(mean - bg).max(2) > 0.06)
    seen, out = np.zeros((h, w), bool), []
    for y0 in range(h):
        for x0 in range(w):
            if not plain[y0, x0] or seen[y0, x0]:
                continue
            colour, stack, cells = mean[y0, x0], [(y0, x0)], []
            seen[y0, x0] = True
            while stack:
                y, x = stack.pop()
                cells.append((y, x))
                for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                    if 0 <= ny < h and 0 <= nx < w and plain[ny, nx] and not seen[ny, nx] and np.abs(mean[ny, nx] - colour).max() < BLOCK_SAME:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            share = len(cells) / (h * w)
            ys, xs = [c[0] for c in cells], [c[1] for c in cells]
            edges = (min(xs) == 0) + (min(ys) == 0) + (max(xs) == w - 1) + (max(ys) == h - 1)
            if share >= BLOCK_FROM and edges < 2 and len(cells) >= BLOCK_FULL * (max(xs) + 1 - min(xs)) * (max(ys) + 1 - min(ys)):
                out.append({"share": share, "colour": "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in colour),
                            "box": (min(xs) / w, min(ys) / h, (max(xs) + 1 - min(xs)) / w, (max(ys) + 1 - min(ys)) / h)})
    return out


def _bg(img: np.ndarray) -> np.ndarray:
    flat = img.reshape(-1, 3)
    bins = (np.minimum(flat * 8, 7.999).astype(np.int32) * np.array([64, 8, 1])).sum(1)
    return flat[bins == np.bincount(bins, minlength=512).argmax()].mean(0)


def _changing(blocks: list[list[dict]], i: int) -> list[dict]:
    """The plain blocks of sample i whose box is not the same size in the samples beside it (it grows, shrinks, comes
    or goes): an empty box caught mid-animation, not a panel that is meant to be a flat colour."""
    area = lambda b: b["box"][2] * b["box"][3]
    out = []
    for b in blocks[i]:
        steady = True
        for j in (i - 1, i + 1):
            if not 0 <= j < len(blocks):
                continue
            twin = [o for o in blocks[j] if _near(o["colour"], b["colour"])]
            if not twin or min(abs(area(o) - area(b)) for o in twin) > BLOCK_CHANGED * area(b):
                steady = False
        if not steady:
            out.append(b)
    return out


def _near(a: str, b: str) -> bool:
    return max(abs(int(a[k:k + 2], 16) - int(b[k:k + 2], 16)) for k in (1, 3, 5)) <= 14


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
    blocks = [plain_blocks(img, _bg(img)) for _, img in samples]
    moving = [_changing(blocks, i) for i in range(len(samples))]
    flags["block"] = [bool(m) and not flags["empty"][i] for i, m in enumerate(moving)]
    out = []
    for kind, flag in flags.items():
        for a, b in _runs(flag):
            t0, t1 = samples[a][0] - (every if kind == "still" else 0), min(samples[b][0] + (0 if kind == "block" else every), last_end)
            if kind == "still" and (t1 - t0 < min_still or all(flags["empty"][a:b + 1])):
                continue          # a short pause is not dead air; a blank stretch is named as blank
            run = facts[a:b + 1]
            row = {"kind": kind, "start": round(max(t0, 0.0), 3), "end": round(t1, 3), "ending": b == len(samples) - 1}
            if kind == "block":
                big = max((b for m in moving[a:b + 1] for b in m), key=lambda b: b["share"])
                row["block_pct"], row["colour"], row["box"] = round(100 * big["share"], 1), big["colour"], [round(v, 3) for v in big["box"]]
            elif kind == "empty":
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
    if r["kind"] == "block":
        x, y, w, h = r["box"]
        at = f'{r["start"]:g} s' if r["start"] == r["end"] else span
        return (f'{at}: a plain {r["colour"]} box with nothing on it, {r["block_pct"]:g} % of the frame, changing size '
                f'(its middle {round(100 * (x + w / 2))} % across, {round(100 * (y + h / 2))} % down): a card opening before its content?')
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
    or unchanged for `min_still` seconds or more, and whether the film ends on one; and a plain block (a card, panel or shape of one
    colour with nothing on it, 6 % of the frame or more) caught while it grows, shrinks, comes or goes, as when a card opens before its
    content fades in. Also names a subject (layer, group, a rig's
    whole posed body) cut by the frame edge: which, which edge, how much of it is outside, when (a composition only, not `video`). Facts, not verdicts: a held title or a planned
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
    scene = render.look_scene(doc, comp["id"])

    def job_fn(job):
        with tempfile.TemporaryDirectory(prefix="rostrum_empty_") as tmp:
            items = [(t, Path(tmp) / f"s{i}.png") for i, t in enumerate(times)]
            render.small_stills(ctx.tool, scene, items, SAMPLE_W, job.progress)
            rows = scan_pngs(items, every, end, args.get("min_still", 2.0))
        rigs, notes = edge_cut.rig_boxes(doc.data, comp, times)
        cuts = edge_cut.scan(comp, times, rigs, every)
        say = " ".join(s for s in (tell(rows, start, end, every), edge_cut.tell(cuts)) if s)
        return Reply(say, {"stretches": rows, "edge_cuts": cuts, "every": every, "samples": len(times)}, warnings=[*scene.get("warnings", []), *notes])

    return ctx.long(f'look_frame (what: empty) {comp["id"]}', job_fn)
