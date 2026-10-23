"""The render time estimate: the arithmetic (pure functions) and the render_estimate tool, which measures through
rostrum3d.estimate_job (a probe at a quarter of the pixels, kept by scene and settings) and scales it here.

Assumption (said out loud in every reply that uses it): a frame's drawing time grows in step with the pixels, and with the samples only
as far as the probe's two sample counts show (denoise and film don't), past a fixed part per frame; start-up (engine, scene, warm-up) and encoding don't, so the settings that
"fit" are a close guide, not a promise."""
from __future__ import annotations

import math

from rostrum_core.mcp import Reply, Tools

from rostrum3d import estimate_job
from rostrum3d.render_fields import QUALITIES, SIZES, settings as shot_settings
from . import draw
from .shot import ITEM_SHOT, doc_and_shot

tools = Tools()

ENCODE_S_PER_FRAME = 0.15         # ffmpeg, libx264 preset slow, crf 14, at HD: a rough figure, not measured per machine
HD_PIXELS = 1920 * 1080             # ENCODE_S_PER_FRAME is for a frame this big; encoding follows the pixels
WARM_PROBE_MS = 3000              # a probe faster than this is cheap enough to render twice (the first absorbs scene load / kernel compile)


def total_seconds(probe_ms: float, frames: int, encode_s_per_frame: float = ENCODE_S_PER_FRAME) -> float:
    """Estimated whole-job seconds: every frame costs the probe, plus encoding."""
    return frames * (probe_ms / 1000 + encode_s_per_frame)


def fitting_settings(estimate_s: float, budget_s: float, renderer: str, samples: int, width: int) -> list[dict]:
    """Concrete lower settings that should fit `budget_s`, each changing one thing: [{"change": "samples", "to": 48, "text": "…"}].
    Empty when nothing can fit by lowering that setting alone."""
    if estimate_s <= budget_s or estimate_s <= 0:
        return []
    k = budget_s / estimate_s                                   # the share of the time that is allowed
    out = []
    if renderer == "cycles" and (s := math.floor(samples * k)) >= 1:
        out.append({"change": "samples", "to": s, "text": f"samples {s} (now {samples})"})
    if (w := math.floor(width * math.sqrt(k) / 2) * 2) >= 64:
        out.append({"change": "width", "to": w, "text": f"width {w} (now {width})"})
    if renderer == "cycles":
        out.append({"change": "quality", "to": "fast", "text": "quality fast (Storm, a draft; far quicker)"})
    return out


def over_budget_text(estimate_s: float, budget_s: float, fits: list[dict]) -> str:
    texts = "; ".join(f["text"] for f in fits) or "nothing small enough by one setting alone: shorten the range with start / end"
    return (f"is estimated at {estimate_s / 60:.1f} min, over the {budget_s / 60:.1f} min budget. Try one of: {texts}. "
            "(Assumption: time follows samples and pixels; denoising and encoding do not shrink, so allow some margin.)")


def scale(m: dict, s: dict, frames: int, mp4: bool) -> dict:
    """The job's time from a measurement (estimate_job) for settings `s` (render_fields.settings) and `frames` frames:
    start-up once (engine, scene, warm-up), then each frame's fixed part plus its pixels × samples part, plus encoding."""
    per_px = max(0.0, m["per_px_ms"] + m.get("per_px_sample_ms", m["per_px_ms"] / m["samples"]) * (s["samples"] - m["samples"])) if m.get("samples") else m["per_px_ms"]
    per_frame = (m["fixed_ms"] + per_px * s["width"] * s["height"]) / 1000
    start = (m["load_ms"] + m["warmup_ms"]) / 1000
    encode = ENCODE_S_PER_FRAME * frames * s["width"] * s["height"] / HD_PIXELS if mp4 else 0.0
    total = start + per_frame * frames + encode
    parts = {"start-up (engine, scene, first-frame warm-up)": start, "drawing the frames": per_frame * frames, "encoding the mp4": encode}
    return {"seconds": round(total, 1), "seconds_per_frame": round(per_frame, 3), "start_s": round(start, 1), "encode_s": round(encode, 1),
            "frames": frames, "slowest_part": max(parts, key=parts.get), "text": sheet_text(total, frames, per_frame)}


def human(sec: float) -> str:
    return f"{sec:.0f} s" if sec < 90 else f"{sec / 60:.0f} min" if sec < 5400 else f"{sec / 3600:.1f} h"


def sheet_text(total: float, frames: int, per_frame: float) -> str:
    """The sheet's Estimate row: "About 6 min · 120 frames · 3 s a frame" (a still: "About 40 s")."""
    per = f"{per_frame:.1f} s a frame" if per_frame < 10 else f"{human(per_frame)} a frame"
    return f"About {human(total)}" + (f" · {frames} frames · {per}" if frames > 1 else "")


OVERRIDES = {
    "frame": {"type": "integer", "minimum": 0, "description": "Estimate a still of this shot frame instead of the shot's frames."},
    "quality": {"enum": [*QUALITIES, "custom"], "description": "Instead of the shot's own: draft 32 samples, good 128, final 512."},
    "samples": {"type": "integer", "minimum": 1, "maximum": 8192, "description": "Instead of the shot's own (sets quality custom)."},
    "denoise": {"type": "boolean", "description": "Noise clean-up, instead of the shot's own (sets quality custom)."},
    "size": {"enum": list(SIZES), "description": "Instead of the shot's own: full, half or double the shot's frame size."},
    "start": {"type": "number", "minimum": 0, "description": "Seconds from the start of the shot (with end: a range instead of the shot's own)."},
    "end": {"type": "number", "minimum": 0, "description": "Seconds from the start of the shot; the frame at this time is the last one."},
}
TO_FIELD = {"quality": "renderQuality", "samples": "renderSamples", "denoise": "renderDenoise", "size": "renderSize",
            "start": "renderStart", "end": "renderEnd"}


def settings_of(shot: dict, info: dict, args: dict) -> dict:
    """The shot's stored render settings with the call's overrides on top: the same reading the Render button makes."""
    over = {TO_FIELD[k]: args[k] for k in TO_FIELD if k in args}
    if "samples" in args or "denoise" in args:
        over.setdefault("renderQuality", "custom")
    if "start" in args or "end" in args:
        over["renderRange"] = "range"
    s = shot_settings({**shot, **over}, info)
    if "frame" in args:
        s["start"] = s["end"] = args["frame"]
    return s


@tools.tool("render_estimate", {"properties": {**ITEM_SHOT, **OVERRIDES,
                                                "all_shots": {"type": "boolean", "default": False, "description": "Every shot of the document, each with its own settings, and a total."},
                                                "budget_min": {"type": "number", "exclusiveMinimum": 0, "description": "Minutes you can spend: over it, the reply names one-setting changes that fit."}}})
def render_estimate(ctx, args):
    """How long a render will take, measured on this machine, without starting it: for a shot (its stored render settings:
    quality, size, frames; any of them overridden here), a still (`frame`), or all shots. The first call for a scene renders a
    probe (the middle frame at a quarter of the pixels, through the same engine path as the real render) and keeps it, so
    asking again, or changing only samples, size or frames, answers at once; any change to the scene measures again.
    Returns seconds a frame, the total, how it was measured, its slowest part, the probe picture, and settings that fit
    `budget_min`. A probe over its 90 s budget stops and says the job is at least that slow. Another render on the graphics
    card at the same time makes the probe (and the real job) slower. Always a job: ask with inspect_job (wait_s up to 25)."""
    doc, info = doc_and_shot(ctx, args)
    shots = [s["id"] for s in doc.data.get("shots", [])] if args.get("all_shots") else [info["id"]]
    eng = draw.engine_of(ctx)
    make_engine = lambda: type(eng)(eng.exe, eng._env, eng.args)  # noqa: E731  its own engine, like the Render button's
    plan = []
    for sid in shots:
        d, i = doc_and_shot(ctx, {**args, "shot": sid})
        shot = next(s for s in d.data["shots"] if s["id"] == sid)
        plan.append((i, settings_of(shot, i, args), draw.scene_of(d, sid)))

    def job_fn(job):
        rows, total = [], 0.0
        for n, (i, s, scene) in enumerate(plan):
            job.progress(n, len(plan), f"Measuring {i['id']}…")
            m = estimate_job.measure(scene, i, s, ctx.tool, make_engine=make_engine)
            frames = s["end"] - s["start"] + 1
            e = scale(m, s, frames, mp4=frames > 1)
            total += e["seconds"]
            how = ("kept from an earlier probe of this same scene" if m["cached"] else "measured now") + \
                f': frame {m["frame"]} at {m["probe"]["size"][0]}×{m["probe"]["size"][1]} took {m["probe"]["ms"][1] / 1000:.1f} s warm'
            rows.append({"shot": i["id"], **{k: s[k] for k in ("quality", "samples", "denoise", "width", "height", "start", "end")},
                         **e, "how": how, "probe_picture": m["picture"], "measurement": {k: v for k, v in m.items() if k != "picture"}})
        budget = args["budget_min"] * 60 if "budget_min" in args else None
        fits = fitting_settings(total, budget, "cycles", rows[0]["samples"], rows[0]["width"]) if budget and len(rows) == 1 else []
        lines = [f'{r["shot"]}: {r["text"]} ({r["width"]}×{r["height"]}, {r["samples"]} samples; {r["how"]}; slowest part: {r["slowest_part"]}).'
                 for r in rows]
        if len(rows) > 1:
            lines.append(f"All {len(rows)} shots: about {human(total)}.")
        if budget and total > budget:
            lines.append(f"The job {over_budget_text(total, budget, fits)}" if len(rows) == 1 else
                         f"Over the {budget / 60:.1f} min budget: lower a shot's quality or size.")
        return Reply(" ".join(lines), {"shots": rows, "seconds": round(total, 1), "text": f"About {human(total)}", "fits": fits},
                     [r["probe_picture"] for r in rows])

    return ctx.job(f'render_estimate {",".join(shots)}', job_fn, key=f"estimate|{doc.item_id}|{shots}|{args}|{doc.seq}")
