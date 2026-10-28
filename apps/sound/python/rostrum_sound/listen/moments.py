"""moments: does each asked-for moment (a hit, a stop, a drum drop, a climax, a lift, a voice span) come across?

A sync check that only asks "is there an onset within 40 ms" passes a hit that is barely there (sound-fair brief 2:
1.6x a normal note, rank 4) and a stop the band's own beat blurs (brief 3). This reads how a listener would: the hit
against the piece's typical onset, the beat just before a stop, where the drums really fall away before a drop, and
where the loudest moment lands against a climax. Each fault comes back as {kind, at_s, measured, fix} (faults.py words it)."""
from __future__ import annotations

import numpy as np

from .core import load, mono, num
from .dsp_events import find_peaks, onset_strength
from .speech_room import TARGET_DB, room

HOP = 256
NEAR_S = 0.08              # the hit's own onset: the strongest flux within this of the asked time
WEAK_X, WEAK_RANK = 2.5, 3 # a hit under 2.5x a normal onset, or not among the file's 3 strongest, does not stand out
BLUR_BEFORE_S = 1.0        # a stop is blurred when an onset this close before it is nearly as strong (≥ 70 %)
BLUR_SHARE = 0.7
STOP_DROP_DB = 8.0         # after a stop the level should fall at least this far within 0.3–1.0 s
DROP_LATE_X, DROP_MIN_S = 1.5, 0.35   # drums "out" early: the last strong onset more than 1.5 beats' gap (≥ 0.35 s) before
CLIMAX_LATE_S, CLIMAX_EARLY_S = 0.75, 0.5
LIFT_LU = 2.0              # a lift: the 3 s after it at least this much louder than the 3 s before
KINDS = ("hit", "stop", "drop", "climax", "lift", "entry", "voice")


def envelope(m, sr):
    """(onset-strength curve, frame times, onset frames, the typical onset's strength): spectral flux on a mel
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


def _hit_at(env, t, pk, at):
    """(frame, strength) of the strongest onset within NEAR_S of `at`, else None."""
    near = [p for p in pk if abs(t[p] - at) <= NEAR_S]
    return max(((p, float(env[p])) for p in near), key=lambda q: q[1]) if near else None


def _db(seg):
    return 10 * np.log10(float(np.mean(seg.astype(np.float64) ** 2)) + 1e-12)


def _hit(m, sr, ev, at, kind):
    env, t, pk, typ = ev
    h = _hit_at(env, t, pk, at)
    if h is None:
        return [{"kind": f"no_{kind}", "at_s": at, "measured": {"onset_within_ms": NEAR_S * 1000}}]
    if kind == "entry":                 # a part coming back (drums back in): it only has to start on time
        return []
    x = h[1] / typ
    rank = int((env[pk] > h[1]).sum()) + 1
    out = []
    if x < WEAK_X or rank > WEAK_RANK:
        out.append({"kind": f"weak_{kind}", "at_s": num(t[h[0]], 2), "measured": {"times_typical": num(x, 1), "rank": rank, "onsets": len(pk)}})
    if kind == "stop":
        before = [p for p in pk if at - BLUR_BEFORE_S <= t[p] < at - NEAR_S]
        rival = max(before, key=lambda p: env[p]) if before else None
        a = lambda s0, s1: m[max(0, int((at + s0) * sr)):int((at + s1) * sr)]
        fall = _db(a(0.0, 0.25)) - _db(a(0.3, 1.0))
        if (rival is not None and env[rival] >= BLUR_SHARE * h[1]) or fall < STOP_DROP_DB:
            out.append({"kind": "blurred_stop", "at_s": at, "measured": {
                "beat_before_s": num(t[rival], 2) if rival is not None else None,
                "beat_before_share": num(env[rival] / h[1], 2) if rival is not None else None, "fall_after_db": num(fall, 1)}})
    return out


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
    ev = envelope(m, sr)
    out = []
    for mo in moments:
        at, kind = float(mo["at"]), mo.get("kind", "hit")
        if kind in ("hit", "stop", "entry"):
            out += _hit(m, sr, ev, at, kind)
        elif kind == "lift":
            out += _lift(y, sr, at)
        elif kind == "drop":
            out += _drop(m, sr, ev, at)
        elif kind == "climax":
            out += _climax(y, sr, at)
        elif kind == "voice" and mo.get("end") is not None:
            out += _voice(y, sr, at, float(mo["end"]))
    return sorted(out, key=lambda f: f["at_s"])
