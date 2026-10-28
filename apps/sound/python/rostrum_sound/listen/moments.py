"""moments: does each asked-for moment (a hit, a stop, a drum drop, a climax, a lift, a voice span) come across?

A sync check that only asks "is there an onset within 40 ms" passes a hit that is barely there (sound-fair brief 2:
1.6x a normal note, rank 4) and a stop the band's own beat blurs (brief 3). This reads how a listener would: the hit
against the piece's typical onset, the beat just before a stop, where the drums really fall away before a drop, and
where the loudest moment lands against a climax. Hits, stops and entries are read by attack.py (the finished file's
short attack, as a listener hears it, against the piece's typical onset and the bed before it). Each fault comes back
as {kind, at_s, measured} (faults.py words it, with the fix)."""
from __future__ import annotations

import numpy as np

from . import attack
from .core import load, mono, num
from .dsp_events import find_peaks, onset_strength
from .speech_room import TARGET_DB, room

HOP = 256
NEAR_S = attack.NEAR_S     # the hit's own onset: the strongest attack within this of the asked time
WEAK_X, WEAK_RANK = 2.5, 3 # a hit under 2.5x a normal onset, or not among the file's 3 strongest, does not stand out
WEAK_ENTRY_X = 2.0         # drums coming back are heard when their first hit is at least 2x a normal onset
STEP_LU, STEP_X = 10.0, 1.5  # ...or a step 10 LU over the bed with an attack 1.5x a normal one (a loud entry from quiet is heard)
BLUR_BEFORE_S = 1.0        # a stop is blurred when an onset this close before it is nearly as strong (≥ 70 %)
BLUR_SHARE = 0.7
STOP_DROP_DB = 8.0         # after a stop the level should fall at least this far within 0.3–1.0 s
DROP_LATE_X, DROP_MIN_S = 1.5, 0.35   # drums "out" early: the last strong onset more than 1.5 beats' gap (≥ 0.35 s) before
CLIMAX_LATE_S, CLIMAX_EARLY_S = 0.75, 0.5
LIFT_LU = 2.0              # a lift: the 3 s after it at least this much louder than the 3 s before
KINDS = ("hit", "stop", "drop", "climax", "lift", "entry", "voice")


def envelope(m, sr):
    """For the drum-drop check: (onset-strength curve, frame times, onset frames, the typical onset's strength): spectral flux on a mel
    spectrogram, its peaks over a 1 s running median + half its spread, and their median = "a normal note"."""
    env = onset_strength(m, sr, HOP)
    t = np.arange(len(env)) * HOP / sr
    k = max(3, int(sr / HOP) | 1)
    pad = np.pad(env, k // 2, mode="edge")
    run = np.median(np.lib.stride_tricks.sliding_window_view(pad, k), axis=1)[:len(env)]
    pk = find_peaks(env, distance=max(1, int(0.05 * sr / HOP)))
    pk = pk[env[pk] > run[pk] + 0.5 * env.std()]
    typical = float(np.median(env[pk])) if len(pk) else float(env.max() or 1.0)
    return env, t, pk, max(typical, 1e-9)


def _db(seg):
    return 10 * np.log10(float(np.mean(seg.astype(np.float64) ** 2)) + 1e-12)


def _hit(wav, m, sr, at, kind):
    """A hit, stop or entry read by attack.strike (the finished file's ~21 ms attack against the piece's typical
    onset and the bed before it): missing, weak (WEAK_X / WEAK_RANK; an entry only WEAK_ENTRY_X; a big loudness step
    with a fair attack is heard: STEP_LU / STEP_X), a stop blurred."""
    s = attack.strike(wav, at)
    if s is None:
        return [{"kind": f"no_{kind}", "at_s": at, "measured": {"onset_within_ms": NEAR_S * 1000}}]
    weak = s["times_typical"] < WEAK_ENTRY_X if kind == "entry" else s["times_typical"] < WEAK_X or s["rank"] > WEAK_RANK
    weak = weak and not ((s["jump_lu"] or 0) >= STEP_LU and s["times_typical"] >= STEP_X)
    out = [{"kind": f"weak_{kind}", "at_s": at, "measured": {"onset_s": s["at_s"], **{k: v for k, v in s.items() if k != "at_s"}}}] if weak else []
    if kind == "stop":
        c = attack.curves(wav)
        env, t, pk = c["env"], c["t"], c["pk"]
        h = s["times_typical"] * c["typ"]
        before = [p for p in pk if at - BLUR_BEFORE_S <= t[p] < at - NEAR_S]
        rival = max(before, key=lambda p: env[p]) if before else None
        a = lambda s0, s1: m[max(0, int((at + s0) * sr)):int((at + s1) * sr)]
        fall = _db(a(0.0, 0.25)) - _db(a(0.3, 1.0))
        if (rival is not None and env[rival] >= BLUR_SHARE * h) or fall < STOP_DROP_DB:
            out.append({"kind": "blurred_stop", "at_s": at, "measured": {
                "beat_before_s": num(t[rival], 2) if rival is not None else None,
                "beat_before_share": num(env[rival] / h, 2) if rival is not None else None, "fall_after_db": num(fall, 1)}})
    return out


def strengths(wav, moments) -> list[dict]:
    """Every timed asked moment (hit, stop, entry) with how it strikes (attack.strike; None: nothing starts there), so a
    reply can show the weakest even when none is a fault."""
    return [{"at": float(mo["at"]), "kind": mo.get("kind", "hit"), "strike": attack.strike(wav, float(mo["at"]))}
            for mo in moments if mo.get("kind", "hit") in ("hit", "stop", "entry")]


def _drop(m, sr, ev, at):
    """Drums out at `at`: the last onset at least half as strong as the typical one in the 4 s before, and the beat
    gap there. Early when the gap to `at` is over 1.5 of those gaps (and 0.35 s)."""
    env, t, pk, typ = ev
    before = [p for p in pk if at - 4.0 <= t[p] <= at + NEAR_S and env[p] >= 0.5 * typ]
    if len(before) < 3:
        return []
    times = np.array([t[p] for p in before])
    gap = float(np.median(np.diff(times))) if len(times) > 2 else 0.5
    early = at - times[-1]
    if early > max(DROP_MIN_S, DROP_LATE_X * gap):
        return [{"kind": "early_drop", "at_s": at, "measured": {"last_beat_s": num(times[-1], 2), "early_s": num(early, 2), "beat_gap_s": num(gap, 2)}}]
    return []


def _lift(y, sr, at):
    """A section lift is heard as the music growing, not as one onset: the 3 s after against the 3 s before."""
    from .bs1770 import integrated
    cut = lambda s0, s1: integrated(y[max(0, int((at + s0) * sr)):int((at + s1) * sr)], sr)
    rise = cut(0.0, 3.0) - cut(-3.0, 0.0)
    return [{"kind": "flat_lift", "at_s": at, "measured": {"rise_lu": num(rise, 1)}}] if rise < LIFT_LU else []


def _climax(y, sr, at):
    """Where the loudest 0.4 s lands against `at` (the 0.4 s window that starts nearest it is the climax's)."""
    from .loudness import loudest
    lo = loudest(y, sr)["momentary_0_4s"]
    off = lo["from_s"] - at
    if off > CLIMAX_LATE_S or off < -CLIMAX_EARLY_S:
        return [{"kind": "late_climax" if off > 0 else "early_climax", "at_s": at,
                 "measured": {"loudest_from_s": lo["from_s"], "off_s": num(off, 2), "loudest_lufs": lo["lufs"]}}]
    return []


def _voice(y, sr, at, end):
    r = room(y[int(at * sr):int(end * sr)], sr)
    gap = r.get("db")
    if gap is not None and gap < TARGET_DB:
        return [{"kind": "busy_speech_band", "at_s": at, "measured": {"to_s": end, "room_db": num(gap, 1)}}]
    return []


def check(wav, moments) -> list[dict]:
    """moments: [{"at": s, "kind": one of KINDS, "end": s (voice only)}] -> the faults found, in time order."""
    y, sr = load(wav)
    m = mono(y)
    ev = envelope(m, sr) if any(mo.get("kind") == "drop" for mo in moments) else None
    out = []
    for mo in moments:
        at, kind = float(mo["at"]), mo.get("kind", "hit")
        if kind in ("hit", "stop", "entry"):
            out += _hit(wav, m, sr, at, kind)
        elif kind == "lift":
            out += _lift(y, sr, at)
        elif kind == "drop":
            out += _drop(m, sr, ev, at)
        elif kind == "climax":
            out += _climax(y, sr, at)
        elif kind == "voice" and mo.get("end") is not None:
            out += _voice(y, sr, at, float(mo["end"]))
    return sorted(out, key=lambda f: f["at_s"])
