"""faults: what a listener would complain about, each named with its time, the measured number and what to change.

Numbers alone let weak results through (sound-fair benchmark: a hit 1.6x a normal note, a stop the band's beat blurred,
"one flat tone held for 29 s", a quiet build squashing the hit, a mono lo-fi mix). This turns the measurements into
faults an agent can act on: [{kind, at_s, measured, words}], and one line for the reply. The asked-for moments (hit,
stop, drop, climax, lift, voice span) are read in moments.py; the whole-piece faults here. Facts, not taste: a fault
says what is measured and the usual ways to change it; a drone that is meant to be a drone may stay."""
from __future__ import annotations

import numpy as np

from .core import load, mono, num
from .dsp import resample
from .dsp_events import chroma
from .memo import remembered
from .moments import check as moment_faults

HELD_S = 12.0          # one harmony (pitch classes, ≥ 0.9 alike every second) held this long reads as one flat tone
HELD_ALIKE = 0.9
HELD_MOVED_DB = 12.0   # ...unless its level moves this much (a long swell or a fade is movement the ear follows)
MONO_CORR = 0.9        # left and right this alike: the mix is near mono (wide mixes measure 0.4–0.8)
SQUASH_DB = 3.0        # the master's limiter holding one moment down this far flattens its attack
_SR = 22050
_HOP = 2048
_BLOCK = 11            # chroma frames per block (about 1 s)


def held_spans(y, sr) -> list[dict]:
    """Stretches where the harmony does not move: every ~1 s block's pitch-class shape within HELD_ALIKE (cosine) of
    the stretch's mean, the sound audible (> -50 dBFS), for HELD_S or longer, its level moving under HELD_MOVED_DB.
    The longest first, non-overlapping."""
    m = resample(mono(y), sr, _SR) if sr != _SR else mono(y)
    c = chroma(m, _SR, _HOP)
    nb = c.shape[1] // _BLOCK
    if nb < 2:
        return []
    cb = c[:, :nb * _BLOCK].reshape(12, nb, _BLOCK).mean(axis=2)
    cb = cb / (np.linalg.norm(cb, axis=0, keepdims=True) + 1e-12)
    blk = _BLOCK * _HOP
    lv = np.array([10 * np.log10(np.mean(m[i * blk:(i + 1) * blk].astype(np.float64) ** 2) + 1e-12) for i in range(nb)])
    sec = blk / _SR
    spans, s = [], 0
    for i in range(1, nb + 1):
        while s < i:
            mean = cb[:, s:i].mean(axis=1)
            mean /= np.linalg.norm(mean) + 1e-12
            if (mean @ cb[:, s:i]).min() >= HELD_ALIKE and (lv[s:i] > -50).all():
                break
            s += 1
        if (i - s) * sec >= HELD_S and (i == nb or not _still(cb, lv, s, i + 1)) and lv[s:i].max() - lv[s:i].min() < HELD_MOVED_DB:
            spans.append({"from_s": num(s * sec, 1), "to_s": num(i * sec, 1), "seconds": num((i - s) * sec, 1),
                          "level_moved_db": num(float(lv[s:i].max() - lv[s:i].min()), 1)})
            s = i                         # the next span starts after this one
    return sorted(spans, key=lambda r: -r["seconds"])


def _still(cb, lv, s, i):
    """Would the stretch s..i still be one held harmony (so the shorter one is not yet its end)?"""
    mean = cb[:, s:i].mean(axis=1)
    mean /= np.linalg.norm(mean) + 1e-12
    return (mean @ cb[:, s:i]).min() >= HELD_ALIKE and (lv[s:i] > -50).all()


def _correlation(y):
    if y.shape[1] < 2:
        return None
    L, R = y[:, 0].astype(np.float64), y[:, 1].astype(np.float64)
    return float(np.corrcoef(L, R)[0, 1]) if L.std() > 0 and R.std() > 0 else 1.0


def _squashed(y, sr, limiter) -> list[dict]:
    """From the render's limiter result: the deepest moment, if it was held down SQUASH_DB or more, and how far the
    10 s before it sat under it (a quiet build is what makes reaching the loudness target squash the one loud moment)."""
    from .bs1770 import integrated
    w = (limiter or {}).get("worst") or []
    if not w or (w[0].get("reduced_db") or 0) < SQUASH_DB:
        return []
    t = float(w[0]["time_s"])
    at = integrated(y[max(0, int((t - 0.2) * sr)):int((t + 0.2) * sr)], sr)
    before = integrated(y[max(0, int((t - 10) * sr)):max(1, int((t - 1) * sr))], sr)
    drv = [d["track"] for d in w[0].get("drivers") or []][:2]
    return [{"kind": "squashed_hit", "at_s": num(t, 2), "measured": {"reduced_db": w[0]["reduced_db"],
             "build_under_lu": num(at - before, 1) if before > -70 else None, "drivers": drv}}]


def _words(f) -> str:
    k, t, d = f["kind"], f["at_s"], f["measured"]
    what = k.split("_", 1)[-1]
    if k.startswith("weak_"):
        return (f"weak {what} at {t:.2f} s: {d['times_typical']:g}x a normal note (rank {d['rank']} of {d['onsets']} onsets); make it "
                "stand out: a breath of silence just before it, more instruments or a brighter attack on it, a lower build into it")
    if k.startswith("no_"):
        return (f"no {what} at {t:.2f} s: nothing starts within {d['onset_within_ms']:g} ms; put the notes on that time "
                "(look_music events with by_stem names the nearest part)")
    if k == "blurred_stop":
        why = (f"the beat at {d['beat_before_s']:g} s is {100 * d['beat_before_share']:.0f} % as strong"
               if d.get("beat_before_share") is not None and d["beat_before_share"] >= 0.7 else
               f"the sound falls only {d['fall_after_db']:g} dB in the second after it")
        return (f"blurred stop at {t:.2f} s: {why}; rest the band on the beat before, end held notes, ride and pedal "
                "at the stop, keep the hit's own notes short")
    if k == "early_drop":
        return (f"drums drop early at {t:.2f} s: the last beat is at {d['last_beat_s']:g} s, {d['early_s']:g} s before "
                f"(the beats are {d['beat_gap_s']:g} s apart); play up to the drop: a last hit or fill ending on the time")
    if k in ("late_climax", "early_climax"):
        side = "after" if k == "late_climax" else "before"
        fix = ("put the weight on the downbeat: accents and attacks on it, shorter or quieter sustains after, slow-attack "
               "sounds (strings, pads) started a little early" if side == "after" else
               "the build peaks too soon: hold its last bars back so the climax is the top")
        return f"loudest moment {abs(d['off_s']):g} s {side} the climax at {t:.2f} s (loudest 0.4 s from {d['loudest_from_s']:g} s); {fix}"
    if k == "flat_lift":
        return (f"lift at {t:.2f} s barely lifts: {d['rise_lu']:+g} LU over the 3 s before; add parts, open a filter, "
                "raise what comes after or thin the bars before")
    if k == "busy_speech_band":
        return (f"busy speech band {t:g}–{d['to_s']:g} s: a voice stands {d['room_db']:+g} dB over the music in 1–4 kHz "
                "(a voice-over bed wants +6); low-pass pads and keys lower, dip 2–4 kHz, fewer parts there")
    if k == "held_tone":
        return (f"one harmony held {t:g}–{d['to_s']:g} s ({d['seconds']:g} s, level moved {d['level_moved_db']:g} dB): heard as "
                "one flat tone; give it movement: change the chord or bass note every few bars, a moving inner line, "
                "or let the sound open (filter, swells, a second texture)")
    if k == "near_mono":
        return (f"near-mono mix: left/right correlation {d['correlation']:g} (wide mixes 0.4–0.8); pan the mono parts apart "
                "(`width` does nothing to a mono recording), use stereo instruments or a stereo reverb")
    if k == "squashed_hit":
        b = f" the 10 s before sit {d['build_under_lu']:g} LU under it, so" if d.get("build_under_lu") is not None else ""
        by = f" ({', '.join(d['drivers'])})" if d.get("drivers") else ""
        return (f"hit at {t:.2f} s squashed {d['reduced_db']:g} dB by the master limiter:{b} reaching the loudness target "
                f"holds the hit down; raise the build (edit_loudness lift_quiet, or the quiet parts' volumes) or lower "
                f"the hit's parts{by} by about {max(1.0, d['reduced_db'] - 2):.0f} dB")
    return k


@remembered
def _whole(wav) -> list[dict]:
    y, sr = load(wav)
    out = [{"kind": "held_tone", "at_s": s["from_s"], "measured": {k: v for k, v in s.items() if k != "from_s"}}
           for s in held_spans(y, sr)]
    corr = _correlation(y)
    if corr is not None and corr > MONO_CORR:
        out.append({"kind": "near_mono", "at_s": 0.0, "measured": {"correlation": num(corr, 2)}})
    return out


def check(wav, moments=None, limiter=None, whole=True) -> dict:
    """The faults of `wav`: the asked-for `moments` ([{"at", "kind", "end"}], moments.KINDS), and with `whole` the
    whole-piece ones (a held tone, a near-mono mix, a hit the limiter squashed: `limiter` = listen.limiter's result)."""
    found = moment_faults(wav, moments) if moments else []
    if whole:
        found += _whole(wav)
        if limiter:
            y, sr = load(wav)
            found += _squashed(y, sr, limiter)
    found = sorted(found, key=lambda f: f["at_s"])
    for f in found:
        f["words"] = _words(f)
    asked = f" (checked {len(moments)} asked moment{'s' * (len(moments) != 1)})" if moments else ""
    said = ("Faults: " + "; ".join(f["words"] for f in found) + ".") if found else f"No faults found{asked}."
    return {"faults": found, "words": said}
