"""The render time estimate: the arithmetic (pure functions) and the render_estimate tool, which measures through
rostrum3d.estimate_job (a probe at a quarter of the pixels and one few-sample frame at the real size, kept by scene and
settings) and scales it here; a busy graphics card is said in the reply.

Assumption (said out loud in every reply that uses it): a frame's drawing time is a fixed part plus a part per pixel (the line
through the probe's quarter-size and real-size frames), and grows with the samples along the real-size frame's measured curve
(straight in the log of the samples; denoise and film don't grow); start-up (engine, scene, warm-up) and encoding don't, so the
settings that "fit" are a close guide, not a promise."""
from __future__ import annotations

import math

from rostrum_core.mcp import Reply, Tools

from rostrum3d import estimate_job, estimate_learn
from rostrum3d.render_fields import QUALITIES, SIZES, settings as shot_settings
from . import draw
from .shot import ITEM_SHOT, doc_and_shot

tools = Tools()

ENCODE_S_PER_FRAME = 0.15         # ffmpeg, libx264 preset slow, crf 14, at HD: a rough figure, not measured per machine
HD_PIXELS = 1920 * 1080             # ENCODE_S_PER_FRAME is for a frame this big; encoding follows the pixels


def fitting_settings(estimate_s: float, budget_s: float, renderer: str, samples: int, width: int, at=None) -> list[dict]:
    """Concrete lower settings that should fit `budget_s`, each changing one thing: [{"change": "samples", "to": 48, "text": "…"}].
    `at(change, value)`: the job's seconds with that one change (`seconds_at`, from the measurement), so the suggestion follows the
    measured cost (time grows much less than in step with samples); without it, in step with samples and pixels.
    Empty when nothing can fit by lowering that setting alone."""
    if estimate_s <= budget_s or estimate_s <= 0:
        return []
    k = budget_s / estimate_s                                   # the share of the time that is allowed
    fit = lambda change, v: at(change, v) <= budget_s           # noqa: E731
    out = []
    s = renderer == "cycles" and (_largest(1, samples - 1, lambda n: fit("samples", n)) if at else math.floor(samples * k))
    if s and s >= 1:
        out.append({"change": "samples", "to": s, "text": f"samples {s} (now {samples})" + (f", about {human(at('samples', s))}" if at else "")})
    w = (_largest(32, width // 2 - 1, lambda x: fit("width", 2 * x)) or 0) * 2 if at else math.floor(width * math.sqrt(k) / 2) * 2
    if w >= 64:
        out.append({"change": "width", "to": w, "text": f"width {w} (now {width})" + (f", about {human(at('width', w))}" if at else "")})
    if renderer == "cycles":
        out.append({"change": "quality", "to": "fast", "text": "quality fast (Storm, a draft; far quicker)"})
    return out


def _largest(lo: int, hi: int, ok) -> int | None:
    """The largest n in lo..hi with ok(n), for an ok that holds up to some n and not past it; None when ok(lo) fails."""
    if hi < lo or not ok(lo):
        return None
    while lo < hi:
        mid = (lo + hi + 1) // 2
        lo, hi = (mid, hi) if ok(mid) else (lo, mid - 1)
    return lo


def seconds_at(m: dict, s: dict, frames: int, mp4: bool):
    """at(change, value) for fitting_settings: the job's seconds with samples or width (the height following) changed."""
    def at(change: str, v: int) -> float:
        t = {**s, "samples": v} if change == "samples" else {**s, "width": v, "height": max(2, round(s["height"] * v / s["width"] / 2) * 2)}
        return scale(m, t, frames, mp4)["seconds"]
    return at


def over_budget_text(estimate_s: float, budget_s: float, fits: list[dict]) -> str:
    texts = "; ".join(f["text"] for f in fits) or "nothing small enough by one setting alone: shorten the range with start / end"
    return (f"is estimated at {estimate_s / 60:.1f} min, over the {budget_s / 60:.1f} min budget. Try one of: {texts}. "
            "(Measured on this machine; start-up and encoding do not shrink, and a busy graphics card is slower, so allow some margin.)")


def sample_factor(m: dict, samples: int) -> float:
    """A frame's time at `samples` over its time at the probe's samples: the probe's measured sample curve
    (estimate_job), straight between its points on a log scale of samples, carried on past them; below its first point
    in step with samples. No curve (Storm, or few samples): in step with samples. Never lower for more samples (a noisy
    curve point above 1 is held at 1), so asking for fewer samples never estimates longer."""
    S, pts = m.get("samples") or 0, m.get("curve") or []
    if not S or not samples:
        return 1.0                                               # Storm: no samples
    if len(pts) < 2:
        return samples / S
    pts = [[n, min(v, 1.0)] if n < S else [n, v] for n, v in pts]
    if samples <= pts[0][0]:
        return pts[0][1] * samples / pts[0][0]
    (n0, v0), (n1, v1) = next(((a, b) for a, b in zip(pts, pts[1:]) if samples <= b[0]), pts[-2:])
    return v0 + (v1 - v0) * math.log(samples / n0) / math.log(n1 / n0)


def scale(m: dict, s: dict, frames: int, mp4: bool) -> dict:
    """The job's time from a measurement (estimate_job) for settings `s` (render_fields.settings) and `frames` frames:
    start-up once (engine, scene, warm-up), then each frame's fixed part plus its pixels × samples part, plus encoding."""
    px, pq = s["width"] * s["height"], math.prod(m["probe"]["size"]) if "probe" in m else 0
    line = m["fixed_ms"] + m["per_px_ms"] * px                  # between the probe's two sizes: the measured line
    floor = (m["fixed_ms"] + m["per_px_ms"] * pq) * px / pq if pq else 0.0   # under the quarter: in step with the pixels
    per_frame = max(line, floor, 0.0) / 1000 * sample_factor(m, s.get("samples", 0)) + m.get("change_ms", 0.0) / 1000 * (frames > 1)   # + the scene moving on to each new frame
    per_frame *= 2 if "shadow" in s.get("passes", ()) else 1     # the Shadow pass draws each frame twice (core passes.h)
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
    "quality": {"enum": [*QUALITIES, "stylized", "custom"], "description": "Instead of the shot's own: draft 32 samples, good 128, final 512 (Cycles); stylized = the stylized renderer (lines, halftone, light to colour), 2× supersampled."},
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
    probe (the middle frame at a quarter of the pixels, and once at the real size with few samples, through the same engine
    path as the real render) and keeps it, so
    asking again, or changing only samples, size or frames, answers at once; any change to the scene measures again.
    The per-frame time includes the scene changing from frame to frame (a cloth or fall's stored shape, animation: one extra small frame is timed at the next frame), and is raised when the last full render of the same shot in this project took 10 %+ over its estimate (the reply says "raised ×N").
    Returns seconds a frame, the total, how it was measured, its slowest part, the probe picture, and settings that fit
    `budget_min`. A probe over its 90 s budget stops and says the job is at least that slow. When another job is using the
    graphics card the reply says so (`gpu_busy`): the render is slower while it runs, and a probe taken then is not kept.
    Always a job: ask with inspect_job (wait_s up to 25)."""
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
        rows, total, at = [], 0.0, None
        for n, (i, s, scene) in enumerate(plan):
            job.progress(n, len(plan), f"Measuring {i['id']}…")
            m = estimate_job.measure(scene, i, s, ctx.tool, make_engine=make_engine)
            frames = s["end"] - s["start"] + 1
            e = estimate_learn.apply(scale(m, s, frames, mp4=frames > 1), estimate_learn.key(ctx.app.folder, doc.item_id, i["id"], s["renderer"]))
            at = (lambda a, k: lambda c, v: a(c, v) * k)(seconds_at(m, s, frames, frames > 1), e.get("learned", 1.0))
            total += e["seconds"]
            how = ("kept from an earlier probe of this same scene" if m["cached"] else "measured now") + \
                f': frame {m["frame"]} at {m["probe"]["size"][0]}×{m["probe"]["size"][1]} took {m["probe"]["ms"][1] / 1000:.1f} s warm' + \
                (f', at {m["full"]["size"][0]}×{m["full"]["size"][1]} with {m["full"]["samples"]} samples {m["full"]["ms"] / 1000:.1f} s' if "full" in m else "")
            how += f"; {estimate_learn.words(e)}" if e.get("learned") else ""
            rows.append({"shot": i["id"], **{k: s[k] for k in ("quality", "samples", "denoise", "width", "height", "start", "end")},
                         **e, "how": how, "gpu_busy": estimate_job.card_note(m), "probe_picture": m["picture"],
                         "measurement": {k: v for k, v in m.items() if k != "picture"}})
        budget = args["budget_min"] * 60 if "budget_min" in args else None
        fits = fitting_settings(total, budget, plan[0][1]["renderer"], rows[0]["samples"], rows[0]["width"], at) if budget and len(rows) == 1 else []
        lines = [f'{r["shot"]}: {r["text"]} ({r["width"]}×{r["height"]}, {r["samples"]} samples; {r["how"]}; slowest part: {r["slowest_part"]}).'
                 for r in rows]
        if note := next((r["gpu_busy"] for r in rows if r["gpu_busy"]), ""):
            lines.append(note)
        if len(rows) > 1:
            lines.append(f"All {len(rows)} shots: about {human(total)}.")
        if budget and total > budget:
            lines.append(f"The job {over_budget_text(total, budget, fits)}" if len(rows) == 1 else
                         f"Over the {budget / 60:.1f} min budget: lower a shot's quality or size.")
        return Reply(" ".join(lines), {"shots": rows, "seconds": round(total, 1), "text": f"About {human(total)}", "fits": fits,
                                       "gpu_busy": note},
                     [r["probe_picture"] for r in rows])

    return ctx.job(f'render_estimate {",".join(shots)}', job_fn, key=f"estimate|{doc.item_id}|{shots}|{args}|{doc.seq}")
