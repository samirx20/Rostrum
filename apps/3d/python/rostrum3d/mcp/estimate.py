"""The arithmetic behind render_video's time estimate: pure functions, no engine.

Assumption (said out loud in every reply that uses it): render time grows in step with the samples and with the number of pixels.
Denoising, scene loading and encoding do not, so the settings that "fit" are a close guide, not a promise."""
from __future__ import annotations

import math

ENCODE_S_PER_FRAME = 0.15         # ffmpeg, libx264 preset slow, crf 14, at HD: a rough figure, not measured per machine
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
