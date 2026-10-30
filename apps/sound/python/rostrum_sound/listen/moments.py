"""moments: does each asked-for moment (a hit, a stop, a drum drop, a climax, a lift, a voice span) come across?

A sync check that only asks "is there an onset within 40 ms" passes a hit that is barely there (sound-fair brief 2:
1.6x a normal note, rank 4) and a stop the band's own beat blurs (brief 3). This reads how a listener would: the hit
against the piece's typical onset and the 2 s before it, the beat just before a stop and how much of the band goes on
after it (stop_fall.py), where the drums really fall away before a drop and whether they are gone in its gap
(drop_gap.py), and where the loudest moment lands against a climax. Hits, stops and entries are read by attack.py (the finished file's
short attack, as a listener hears it, against the piece's typical onset and the bed before it). Each fault comes back
as {kind, at_s, measured} (faults.py words it, with the fix)."""
from __future__ import annotations

import numpy as np

from . import attack, drop_gap, rise_gap, stop_fall
from . import rival as rival_attack
from .brightness import growth
from .core import load, mono, num
from .dsp_events import find_peaks, onset_strength
from .speech_room import TARGET_DB, room

HOP = 256
NEAR_S = attack.NEAR_S     # the hit's own onset: the strongest attack within this of the asked time
WEAK_X, WEAK_RANK = 2.5, 3 # a hit under 2.5x a normal onset, or not among the file's 3 strongest, does not stand out
WEAK_ENTRY_X = 2.0         # drums coming back are heard when their first hit is at least 2x a normal onset
STEP_LU, STEP_X = 10.0, 1.5  # ...or a step 10 LU over the bed with an attack 1.5x a normal one (a loud entry from quiet is heard)
CONTRAST_DB, CONTRAST_PEAK_DB = 12.0, 10.0  # ...or 12 dB over the 2 s before, peak 10 dB over the bed's, attack ≥ 1x: jumps out
BLUR_BEFORE_S = 1.0        # a stop is blurred when an onset this close before it is nearly as strong (≥ 70 %)
BLUR_SHARE = 0.7
STOP_DROP_DB = 8.0         # after a stop the level should fall at least this far within 0.3–1.0 s
DROP_LATE_X, DROP_MIN_S = 1.5, 0.35   # drums "out" early: the last strong onset more than 1.5 beats' gap (≥ 0.35 s) before
CLIMAX_LATE_S, CLIMAX_EARLY_S = 3.0, 0.5   # an orchestra blooms 1–2 s after a tutti downbeat: only over 3 s is late
HOLD_S = 3                 # a climax holds while each 1 s after it is at least as loud as the 3 s before; under 3 s it is cut short
CEILING_NEAR_DB, CEILING_DBFS = 1.5, -3.0  # the build's peak within 1.5 dB of a file peak at -3 dBFS or more: at the ceiling
LIFT_LU = 2.0              # a lift: the 3 s after it at least this much louder than the 3 s before
QUIET_LUFS = -70.0         # a stretch quieter than this (or past the file's end) is measured as this: silence, not -inf
GROW_DB = 6.0              # the top end of a climax or lift at least this much brighter than the start (open builds: +11 to +15)
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
    stands = ((s.get("over_before_db") or 0) >= CONTRAST_DB and (s.get("peak_over_bed_db") or 0) >= CONTRAST_PEAK_DB
              and s["times_typical"] >= 1.0)       # a swell with no attack (a low boom) is not heard as a hit, however loud
    weak = weak and not ((s["jump_lu"] or 0) >= STEP_LU and s["times_typical"] >= STEP_X) and not stands
    out = [{"kind": f"weak_{kind}", "at_s": at, "measured": {"onset_s": s["at_s"], **{k: v for k, v in s.items() if k != "at_s"}}}] if weak else []
    if kind in ("hit", "climax") and not weak and at_ceiling(s):     # a weak one's fixes lead with headroom already
        out.append({"kind": "build_at_ceiling", "at_s": at, "measured": {k: s[k] for k in ("build_peak_db", "file_peak_db", "headroom_db")}})
    if kind in ("hit", "climax"):                    # a stronger attack just before takes the moment (rival.py)
        out += rival_attack.faults(wav, at, kind, s)
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
                "beat_before_share": num(env[rival] / h, 2) if rival is not None else None, "fall_after_db": num(fall, 1),
                **stop_fall.measure(m, sr, at)}})
    return out


def at_ceiling(s) -> bool:
    """The build into the moment already peaks at the file's ceiling (attack.strike's numbers): it cannot be louder."""
    return s["file_peak_db"] >= CEILING_DBFS and s["headroom_db"] < CEILING_NEAR_DB


def strengths(wav, moments) -> list[dict]:
    """Every timed asked moment (hit, stop, entry, climax) with how it strikes (attack.strike; None: nothing starts
    there), so a reply can show the weakest even when none is a fault."""
    return [{"at": float(mo["at"]), "kind": mo.get("kind", "hit"), "strike": attack.strike(wav, float(mo["at"]))}
            for mo in moments if mo.get("kind", "hit") in ("hit", "stop", "entry", "climax")]


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


def lift_rise(wav, at) -> float:
    """A section lift is heard as the music growing, not as one onset: the 3 s after against the 3 s before, in LU."""
    from .bs1770 import integrated
    y, sr = load(wav)
    cut = lambda s0, s1: max(QUIET_LUFS, integrated(y[max(0, int((at + s0) * sr)):int((at + s1) * sr)], sr))
    return cut(0.0, 3.0) - cut(-3.0, 0.0)


def _lift(y, sr, at):
    rise = lift_rise((y, sr), at)
    return [{"kind": "flat_lift", "at_s": at, "measured": {"rise_lu": num(rise, 1)}}] if rise < LIFT_LU else []


def _climax(wav, m, sr, y, at):
    """A climax: its downbeat's attack (as a hit: weak, or the build already at the ceiling), whether it holds (the 3 s
    after against the 3 s before) and where the loudest 0.4 s lands (a bloom up to 3 s after the downbeat is normal)."""
    from .bs1770 import integrated
    from .loudness import loudest
    out = [f for f in _hit(wav, m, sr, at, "climax") if not f["kind"].startswith("no_")]
    cut = lambda s0, s1: max(QUIET_LUFS, integrated(y[max(0, int((at + s0) * sr)):max(1, int((at + s1) * sr))], sr))
    build = cut(-3.5, -0.5)
    held = next((s for s in range(HOLD_S) if cut(s, s + 1) < build), HOLD_S)
    if held < HOLD_S and build > -70:
        out.append({"kind": "short_climax", "at_s": at, "measured": {"held_s": held, "build_lufs": num(build, 1),
                    "then_lu": num(cut(held, held + 1) - build, 1)}})
    lo = loudest(y, sr)["momentary_0_4s"]
    off = lo["from_s"] - at
    if off > CLIMAX_LATE_S or off < -CLIMAX_EARLY_S:
        out.append({"kind": "late_climax" if off > 0 else "early_climax", "at_s": at,
                    "measured": {"loudest_from_s": lo["from_s"], "off_s": num(off, 2), "loudest_lufs": lo["lufs"]}})
    return out


def _flat_top(wav, at):
    """A build heard as opening up gets brighter, not only louder: the top end from the moment against the start."""
    g = growth(wav, at)
    return [{"kind": "flat_top", "at_s": at, "measured": g}] if g and g["grew_db"] < GROW_DB else []


def _voice(y, sr, at, end):
    r = room(y[int(at * sr):int(end * sr)], sr)
    gap = r.get("db")
    if gap is not None and gap < TARGET_DB:
        return [{"kind": "busy_speech_band", "at_s": at, "measured": {"to_s": end, "room_db": num(gap, 1)}}]
    return []


def check(wav, moments, drums=None) -> list[dict]:
    """moments: [{"at": s, "kind": one of KINDS, "end": s (voice: the span; drop: the drums' return, else the first
    entry after it, else drop_gap.DEFAULT_GAP_S)}] -> the faults found, in time order. `drums`: the render's drum
    tracks' own files, so a drop's gap is read on them (drop_gap.py)."""
    y, sr = load(wav)
    m = mono(y)
    ev = envelope(m, sr) if any(mo.get("kind") == "drop" for mo in moments) else None
    out = []
    for mo in moments:
        at, kind = float(mo["at"]), mo.get("kind", "hit")
        if kind in ("hit", "stop", "entry"):
            out += _hit(wav, m, sr, at, kind)
        elif kind == "lift":
            out += _lift(y, sr, at) + _flat_top(wav, at) + rise_gap.faults(y, sr, at)
        elif kind == "drop":
            end = mo.get("end")
            out += _drop(m, sr, ev, at) + drop_gap.faults(m, sr, at, float(end) if end is not None else drop_gap.return_of(moments, at), drums)
        elif kind == "climax":
            out += _climax(wav, m, sr, y, at) + _flat_top(wav, at) + rise_gap.faults(y, sr, at)
        elif kind == "voice" and mo.get("end") is not None:
            out += _voice(y, sr, at, float(mo["end"]))
    return sorted(out, key=lambda f: f["at_s"])
