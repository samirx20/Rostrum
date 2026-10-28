"""The Render button's time, shown the moment it is pressed (SPEC § 1 6:30: it says how long before it starts), and only
when it is measured: never a confident wrong number.

The render sheet's kept measurement of this very scene (estimate_job.cached, scaled by mcp/estimate.scale) is said as
"about …". Without one there is NO number at first, only "measuring the time" and the seconds so far, until the frame's
own step reports give a real rate (left(), a few seconds in). Guesses from elsewhere were tried and were wrong both ways:
the reference laptop's figures leave out a first render's set-up (a 56 s render said "about 9 s"), and this computer's
speed on its last Render belongs to another scene and another load on the machine (a 96 s render said "about 7 s").
"""
from __future__ import annotations

from rostrum3d import estimate_job
from rostrum3d.mcp.estimate import human, scale
from rostrum3d.runtime import find_exe

WRITE_S = 1.0                                           # denoise, PNG + EXR written after the last sample (a rough figure)


def guess(scene: dict, s: dict, exe=None) -> tuple[float, bool]:
    """(seconds, measured?) for one frame with settings `s` (render_fields.settings). Never blocks on the card.
    (0.0, False): nothing measured for this scene yet: show "measuring the time"."""
    try:
        if (m := estimate_job.cached(scene, s, exe or find_exe())) is not None:
            return scale(m, s, 1, mp4=False)["seconds"], True
    except Exception:  # noqa: BLE001  no engine build to key on, an unreadable entry: nothing measured
        pass
    return 0.0, False


def words(seconds: float) -> str:
    """"about 40 s" (measured), or "measuring the time" (no number yet: seconds <= 0)."""
    return "measuring the time" if seconds <= 0 else f"about {human(max(1.0, seconds))}"


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
