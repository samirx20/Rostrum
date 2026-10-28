"""The Render button's time, shown the moment it is pressed (SPEC § 1 6:30: it says how long before it starts): never a
long "Measuring…".

Best first: the render sheet's kept measurement of this very scene (estimate_job.cached, scaled by mcp/estimate.scale:
the measured number). Without one, a first guess from how fast this computer drew its last Render (seconds of drawing
per megapixel at Final, kept in the cache folder). A guess says so ("about …, a first guess"); while the render runs the
job counts the seconds against it, and when it lands its real time is kept here, so the next guess is this computer's own.
With neither (the first Render on a computer) there is NO number: the reference laptop's figures (CURVE) leave out what a
first render spends before its first sample (the scene's set-up, Cycles loading its kernels: a 56 s render was "about
9 s"), so the row says "measuring…" until the frame's own step reports give a real rate (left()), a few seconds in.
"""
from __future__ import annotations

import json
import math

from rostrum_core.cache import CACHE
from rostrum3d import estimate_job
from rostrum3d.mcp.estimate import HD_PIXELS, human, scale
from rostrum3d.runtime import find_exe

FILE = "3d-render-speed.json"
START_S = 6.0                                           # engine start, scene load, first-frame warm-up (reference laptop)
WRITE_S = 1.0                                           # denoise, PNG + EXR written after the last sample (a rough figure)
CURVE = [(8, 2.5), (32, 4.3), (128, 7.6), (512, 10.5)]  # full HD seconds a frame by samples (reference laptop)


def _reference(samples: int) -> float:
    """Full HD seconds a frame at `samples`, straight between CURVE's points on a log scale of samples."""
    samples = max(1, samples)
    if samples <= CURVE[0][0]:
        return CURVE[0][1] * samples / CURVE[0][0]
    (n0, v0), (n1, v1) = next(((a, b) for a, b in zip(CURVE, CURVE[1:]) if samples <= b[0]), CURVE[-2:])
    return v0 + (v1 - v0) * math.log(samples / n0) / math.log(n1 / n0)


def _kept() -> dict:
    try:
        return json.loads((CACHE.root / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def guess(scene: dict, s: dict, exe=None) -> tuple[float, bool]:
    """(seconds, measured?) for one frame with settings `s` (render_fields.settings). Never blocks on the card.
    (0.0, False): nothing real to go on yet (no kept measurement, no speed of this computer): show "measuring…"."""
    try:
        if (m := estimate_job.cached(scene, s, exe or find_exe())) is not None:
            return scale(m, s, 1, mp4=False)["seconds"], True
    except Exception:  # noqa: BLE001  no engine build to key on, an unreadable entry: fall through to a guess
        pass
    per_ref = _kept().get("per_ref")                    # this computer's speed over the reference laptop's, from its last Render
    if not per_ref:
        return 0.0, False
    ref = _reference(s.get("samples", 128)) * s["width"] * s["height"] / HD_PIXELS
    return START_S + ref * float(per_ref), False


def guess_job(scene: dict, s: dict, frames: int, exe=None) -> float:
    """A first guess for `frames` frames: the engine starts once, then each frame (the render sheet while it measures)."""
    one, _ = guess(scene, s, exe)
    if one <= 0:
        return 0.0
    return START_S + (one - START_S) * max(1, frames)


def learn(s: dict, seconds: float):
    """A Render landed in `seconds`: keep this computer's speed for the next first guess."""
    if s.get("renderer", "cycles") != "cycles":
        return                                          # the kept speed is Cycles' (a Stylized render has no samples)
    ref = _reference(s.get("samples", 128)) * s["width"] * s["height"] / HD_PIXELS
    if ref <= 0 or seconds <= 0:
        return
    per_ref = max(0.05, (seconds - START_S) / ref)
    try:
        CACHE.root.mkdir(parents=True, exist_ok=True)
        (CACHE.root / FILE).write_text(json.dumps({"per_ref": round(per_ref, 3)}), encoding="utf-8")
    except OSError:
        pass                                            # only the next guess is worse; the render itself is fine


def words(seconds: float, measured: bool) -> str:
    """"about 40 s" (measured), "about 40 s, a first guess", or "measuring the time" (no number yet: seconds <= 0)."""
    if seconds <= 0:
        return "measuring the time"
    return f"about {human(max(1.0, seconds))}" + ("" if measured else ", a first guess")


def left(first: tuple[float, float], last: tuple[float, float]) -> float | None:
    """Seconds left of a frame from two of Cycles' step reports (share done, ms since the frame began): the rate between
    them, so the frame's set-up before its first samples (scene sync, kernels: seconds on a big clay) doesn't count as
    drawing; plus writing the files. None until 3 % more of the frame and most of a second lie between the two."""
    (f0, ms0), (f1, ms1) = first, last
    if f1 - f0 < 0.03 or ms1 - ms0 < 800:
        return None
    return (ms1 - ms0) / (f1 - f0) * (1 - min(f1, 1.0)) / 1000 + WRITE_S


def words_left(seconds: float) -> str:
    """"about 25 s left" (measured on the frame being drawn), "almost done" in its last seconds."""
    return "almost done" if seconds < 2 else f"about {human(seconds)} left"
