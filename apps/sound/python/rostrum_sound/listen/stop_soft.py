"""stop_soft: an asked stop that lands soft, said as one fault with the fix the measurements point to.

moments.py finds a stop whose attack is not clearly the band's strongest arrival (weak_stop) or whose next second is
not clearly quieter (blurred_stop). Round 2's jazz stop measured 1.2x a normal note because the ride's peaks made the
master limiter pull 8.7 dB there: the usual stop fixes could not help until the peaks were tamed. This merges the two
faults of one stop into a "soft_stop" and, when the limiter pulls SQUASH_DB or more around it (listen/limiter.py's
curve), leads the fix with a compressor on the track driving it (or lower ride / cymbal velocity) before maxLimit."""
from __future__ import annotations

import numpy as np

from . import stop_fall
from .core import num

HARD_DB = 3.0            # the limiter pulling this much at the stop flattens it (faults.SQUASH_DB)
AROUND_S = (-0.5, 0.3)   # the limiter's curve read over this span around the stop
STOP_KINDS = ("weak_stop", "blurred_stop")


def _pull(limiter, t) -> tuple[float, list[str]]:
    """The limiter's deepest reduction around `t` and the tracks driving its nearest worst moment."""
    curve = (limiter or {}).get("_curve")
    red = np.asarray([] if curve is None else curve, dtype=np.float64)
    step = (limiter or {}).get("curve_step_s", 0.1)
    a, b = max(0, int((t + AROUND_S[0]) / step)), int((t + AROUND_S[1]) / step) + 1
    deep = float(red[a:b].max()) if red[a:b].size else 0.0
    near = [w for w in (limiter or {}).get("worst") or [] if abs(w["time_s"] - t) <= 1.0]
    drv = [d["track"] for d in (near[0].get("drivers") or [])][:2] if near else []
    return deep, drv


def merge(found: list[dict], limiter=None, peaky=None) -> list[dict]:
    """`found` with each stop's weak_stop / blurred_stop replaced by one soft_stop (their numbers together, plus the
    limiter's pull there and the track to tame)."""
    stops: dict = {}
    for f in found:
        if f["kind"] in STOP_KINDS:
            stops.setdefault(round(f["at_s"], 2), []).append(f)
    out = [f for f in found if f["kind"] not in STOP_KINDS]
    for t, fs in stops.items():
        d = {k: v for f in fs for k, v in f["measured"].items()} | {"weak": any(f["kind"] == "weak_stop" for f in fs)}
        deep, drv = _pull(limiter, t)
        if limiter:
            d |= {"limiter_db": num(deep, 1), "drivers": drv, "tame": (drv[0] if drv else peaky)}
        out.append({"kind": "soft_stop", "at_s": fs[0]["at_s"], "measured": d})
    return out


def words(f) -> str:
    t, d = f["at_s"], f["measured"]
    why = []
    if d.get("weak"):
        why.append(f"its attack is {d['times_typical']:.1f}x a normal note (rank {d['rank']}), not clearly the band's strongest arrival")
    if d.get("beat_before_share") is not None and d["beat_before_share"] >= 0.7:
        why.append(f"the beat at {d['beat_before_s']:g} s is {100 * d['beat_before_share']:.0f} % as strong")
    if d.get("fall_after_db") is not None and d["fall_after_db"] < 8:
        why.append(f"the gap after it falls only {d['fall_after_db']:g} dB, not clearly quieter")
    why += stop_fall.why(d)
    band = ("rest the band on the beat before, put its strongest accent on the stop, then end held notes, ride and "
            "pedal at once (short notes on the stop itself)")
    head = f"stop at {t:.2f} s lands soft: {'; '.join(why) or 'it does not stand out'}"
    if (d.get("limiter_db") or 0) >= HARD_DB:
        by = f" (driven by {', '.join(d['drivers'])})" if d.get("drivers") else ""
        who = d.get("tame")
        call = f'{{"apply": "tame_peaks", "track": "{who}"}}' if who else '{"apply": "tame_peaks"}'
        return (f"{head}; the master limiter pulls {d['limiter_db']:g} dB there{by}, flattening it. Fix first: a compressor "
                f"on {who or 'the most peaked track'} (edit_loudness {call}) or lower velocity on ride and "
                f"cymbals; then {band}; raise maxLimit only after that")
    return f"{head}; fix: {band}; {stop_fall.script_fix(t)}"
