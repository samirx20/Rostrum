"""faults: what a listener would complain about, each named with its time, the measured number and what to change.

Numbers alone let weak results through (sound-fair benchmark: a hit 1.6x a normal note, a stop the band's beat blurred,
"one flat tone held for 29 s", a quiet build squashing the hit, a mono lo-fi mix). This turns the measurements into
faults an agent can act on: [{kind, at_s, measured, words}], and one line for the reply. The asked-for moments (hit,
stop, drop, climax, lift, voice span) are read in moments.py; the whole-piece faults here. Facts, not taste: a fault
says what is measured and the usual ways to change it; a drone that is meant to be a drone may stay."""
from __future__ import annotations

import numpy as np

from .core import load, mono, num
from .brightness import brightest
from .dsp import resample
from .dsp_events import chroma
from .memo import remembered
from .moments import at_ceiling, check as moment_faults
from . import drop_gap, hit_room, lead_in, rise_gap, rival, shelf_try, squash, stop_fall, stop_soft, tempo_fit

NEW_WORDS = {"leading_silence": lead_in.words, "off_tempo": tempo_fit.words, "soft_stop": stop_soft.words,
             "drums_in_gap": drop_gap.words, "early_rival": rival.words,
             "gap_before": rise_gap.words, "squashed_mix": squash.words, "buried_hit": hit_room.words}

HELD_S = 12.0          # one harmony (pitch-class shape, ≥ 0.9 alike every second) held this long reads as one flat tone
HELD_ALIKE = 0.9
HELD_MOVED_DB = 12.0   # ...unless its level moves this much (a long swell or a fade is movement the ear follows)
HELD_PITCHED = 0.35    # ...and only where notes are this share of the sound (55 Hz-4.2 kHz): a drum-only second measured
                       #   0.0-0.32 (a steady hi-hat read as "one harmony held"), real mixes with drums 0.38-1.0
DULL_DB = -20.0       # the brightest tenth of the piece's top end (4–16 kHz) under this against 250 Hz–1 kHz: dull
SHELF_MARGIN, SHELF_MOST_DB = 1.5, 8.0   # dull_top's shelf: tried on the render to reach DULL_DB + this, at most this gain
MONO_CORR = 0.9       # left and right this alike: the mix is near mono (wide mixes measure 0.4–0.8)
SQUASH_DB = 3.0        # the master's limiter holding one moment down this far flattens its attack
_SR = 22050
_HOP = 2048
_BLOCK = 11            # chroma frames per block (about 1 s)


def held_spans(y, sr) -> list[dict]:
    """Stretches where the harmony does not move: every ~1 s block's pitch-class shape within HELD_ALIKE (cosine) of
    the stretch's mean, the sound audible (> -50 dBFS), for HELD_S or longer, its level moving under HELD_MOVED_DB.
    The longest first, non-overlapping. The shape is each block's twelve classes less their own mean: which notes stand
    out, not the floor every class carries in a real mix (reverb, harmonics, a melody, the bass), which made any two
    blocks in one key ≥ 0.9 alike and a ii-V every two beats read as one held harmony. A block counts only where notes
    are HELD_PITCHED of its sound: a drum groove's leftover after the drums are taken out is a steady shape too."""
    m = resample(mono(y), sr, _SR) if sr != _SR else mono(y)
    c, e = chroma(m, _SR, _HOP, pitched=True)
    nb = c.shape[1] // _BLOCK
    if nb < 2:
        return []
    e = np.pad(e, ((0, 0), (0, max(0, nb * 2 * _BLOCK - e.shape[1]))), mode="edge")   # two STFT steps per chroma frame
    eb = e[:, :nb * 2 * _BLOCK].reshape(2, nb, 2 * _BLOCK).sum(axis=2)
    pitched = eb[0] >= HELD_PITCHED * eb[1]
    cb = c[:, :nb * _BLOCK].reshape(12, nb, _BLOCK).mean(axis=2)
    cb = cb - cb.mean(axis=0, keepdims=True)
    cb = cb / (np.linalg.norm(cb, axis=0, keepdims=True) + 1e-12)
    blk = _BLOCK * _HOP
    lv = np.array([10 * np.log10(np.mean(m[i * blk:(i + 1) * blk].astype(np.float64) ** 2) + 1e-12) for i in range(nb)])
    sec = blk / _SR
    spans, s = [], 0
    for i in range(1, nb + 1):
        while s < i:
            mean = cb[:, s:i].mean(axis=1)
            mean /= np.linalg.norm(mean) + 1e-12
            if (mean @ cb[:, s:i]).min() >= HELD_ALIKE and (lv[s:i] > -50).all() and pitched[s:i].all():
                break
            s += 1
        if (i - s) * sec >= HELD_S and (i == nb or not _still(cb, lv, pitched, s, i + 1)) and lv[s:i].max() - lv[s:i].min() < HELD_MOVED_DB:
            spans.append({"from_s": num(s * sec, 1), "to_s": num(i * sec, 1), "seconds": num((i - s) * sec, 1),
                          "level_moved_db": num(float(lv[s:i].max() - lv[s:i].min()), 1)})
            s = i                         # the next span starts after this one
    return sorted(spans, key=lambda r: -r["seconds"])


def _still(cb, lv, pitched, s, i):
    """Would the stretch s..i still be one held harmony (so the shorter one is not yet its end)?"""
    mean = cb[:, s:i].mean(axis=1)
    mean /= np.linalg.norm(mean) + 1e-12
    return (mean @ cb[:, s:i]).min() >= HELD_ALIKE and (lv[s:i] > -50).all() and pitched[s:i].all()


def _correlation(y):
    if y.shape[1] < 2:
        return None
    L, R = y[:, 0].astype(np.float64), y[:, 1].astype(np.float64)
    return float(np.corrcoef(L, R)[0, 1]) if L.std() > 0 and R.std() > 0 else 1.0


def _squashed(y, sr, limiter, asked=()) -> list[dict]:
    """From the render's limiter result: the deepest moment, if it was held down SQUASH_DB or more on an asked moment
    (`asked`: their times; within 1 s), and how far the 10 s before it sat under it (a short loud moment cannot carry
    the loudness target, so the build does and the limiter holds the moment down). A squashed stretch with no asked
    moment on it is the whole mix's (squash.py)."""
    from .bs1770 import integrated
    w = (limiter or {}).get("worst") or []
    if not w or (w[0].get("reduced_db") or 0) < SQUASH_DB:
        return []
    t = float(w[0]["time_s"])
    if not any(abs(t - a) <= 1.0 for a in asked):
        return []
    at = integrated(y[max(0, int((t - 0.2) * sr)):int((t + 0.2) * sr)], sr)
    before = integrated(y[max(0, int((t - 10) * sr)):max(1, int((t - 1) * sr))], sr)
    drv = [d["track"] for d in w[0].get("drivers") or []][:2]
    return [{"kind": "squashed_hit", "at_s": num(t, 2), "measured": {"reduced_db": w[0]["reduced_db"],
             "build_under_lu": num(at - before, 1) if before > -70 else None, "drivers": drv}}]


BRIGHT_X = 2.5        # a hit's 2 kHz-up attack under this many times a normal note's: no crack, it reads as a thud
JUMP_LU = 6.0         # the hit's 0.4 s under this much louder than the 1.5 s before: the bed hides it
BED_X = 2.0           # the hit under this many times the onsets of the 2 s before: the notes into it strike as hard


def heard(d) -> str:
    """The measured numbers of a weak moment (attack.strike), in words."""
    bits = [f"{d['times_typical']:.1f}x a normal note (rank {d['rank']} of {d['onsets']} onsets)", f"bright attack {d['bright_x']:.1f}x"]
    if d.get("times_bed") is not None:
        bits.append(f"{d['times_bed']:.1f}x the notes of the 2 s before")
    bits.append(f"{d['jump_lu']:+.1f} LU over the 1.5 s before" if d.get("jump_lu") is not None else "silence before it")
    if d.get("over_before_db") is not None:
        pk = f", peak {d['peak_over_bed_db']:+.1f} dB over the bed's" if d.get("peak_over_bed_db") is not None else ""
        bits.append(f"{d['over_before_db']:+.1f} dB over the 2 s before{pk} (hits that read: +8 dB or more)")
    return ", ".join(bits)


def shelf_fix(d) -> str:
    """The master high shelf, tried on this render (shelf_try.py): the gain that lifts the brightest tenth over DULL_DB
    with SHELF_MARGIN to spare, or, when even SHELF_MOST_DB falls short, what that reaches and how far short it stays."""
    s = d.get("shelf")
    if not s:
        return "brighten the parts (a shelf could not be measured on this render)"
    code = (f'master.effect("eq", bands=[{{"shape": "highshelf", "freq": 4000, "gain": {s["gain"]:g}, "q": 0.7}}]) in a script '
            f"(+{s['gain']:g} dB over 4 kHz on the whole mix)")
    if s["clears"]:
        return f"or, measured on this render: {code} reaches {s['reaches_db']:g} dB (passes at {DULL_DB:g})"
    return (f"a shelf alone does not clear it: measured on this render, the most a shelf should add, {code}, reaches only "
            f"{s['reaches_db']:g} dB, still {DULL_DB - s['reaches_db']:.1f} dB short of {DULL_DB:g}; change the parts first "
            "(the ways above), then the shelf can add the rest")


def headroom_fix(d) -> str:
    return (f"make headroom: the build already peaks at {d['build_peak_db']:.1f} dBFS, {d['headroom_db']:.1f} dB under the "
            "file's loudest peak, so the hit cannot be louder; keep the build's peaks 4–6 dB under the ceiling (its velocities "
            "or volumes, not the hit's) and let the hit ring or hold 3–5 s so it carries the loudness target "
            "(edit_loudness lift_quiet narrows the range)")


def weak_fixes(t, d) -> list[str]:
    """The changes that answer what measured short, the biggest shortfall first (at most three); headroom first when
    the build already sits at the ceiling (nothing else can make the hit louder)."""
    out = [headroom_fix(d)] if d.get("headroom_db") is not None and at_ceiling(d) else []
    if d["bright_x"] < BRIGHT_X:
        out.append("add a short loud part with a fast bright attack on it (crash, snare, a high piano or brass stab)")
    if d.get("jump_lu") is not None and d["jump_lu"] < JUMP_LU:
        out.append(f"silence or duck the bed for 0.3–0.5 s before it (end its notes by {max(0.0, t - 0.4):.2f} s; in a "
                   f"script m = moment(\"hit\", at={t:g}); m.rest(<the bed's tracks>, before=0.4); m.strike(brass, [\"C2\", \"G2\"], vel=1.0, ring=4.0))")
    if d.get("times_bed") is not None and d["times_bed"] < BED_X:
        out.append("shorten the bed's notes into it and strike nothing on the beat before")
    if len(out) < 3:
        out.append("put more instruments on it, spread across registers (low, middle, high)")
    return out[:3]


def _words(f) -> str:
    k, t, d = f["kind"], f["at_s"], f["measured"]
    if k in NEW_WORDS:
        return NEW_WORDS[k](f)
    what = k.split("_", 1)[-1]
    if k.startswith("weak_"):
        return f"weak {what} at {t:.2f} s: {heard(d)}; fix: {'; '.join(weak_fixes(t, d))}"
    if k.startswith("no_"):
        return (f"no {what} at {t:.2f} s: nothing starts within {d['onset_within_ms']:g} ms; put the notes on that time "
                "(look_music events with by_stem names the nearest part)")
    if k == "blurred_stop":
        why = (f"the beat at {d['beat_before_s']:g} s is {100 * d['beat_before_share']:.0f} % as strong"
               if d.get("beat_before_share") is not None and d["beat_before_share"] >= 0.7 else
               f"the sound falls only {d['fall_after_db']:g} dB in the second after it")
        why = "; ".join([why] + stop_fall.why(d))
        return (f"blurred stop at {t:.2f} s: {why}; rest the band on the beat before, end held notes, ride and pedal "
                f"at the stop, keep the hit's own notes short; {stop_fall.script_fix(t)}")
    if k == "early_drop":
        return (f"drums drop early at {t:.2f} s: the last beat is at {d['last_beat_s']:g} s, {d['early_s']:g} s before "
                f"(the beats are {d['beat_gap_s']:g} s apart); play up to the drop: a last hit or fill ending on the time")
    if k == "build_at_ceiling":
        return (f"the build into {t:.2f} s already reaches the ceiling: its peak in the 3 s before is {d['build_peak_db']:g} dBFS, "
                f"{d['headroom_db']:g} dB under the file's loudest ({d['file_peak_db']:g}); keep the build's peaks 4–6 dB under "
                "and let the moment ring or hold 3–5 s so it carries the loudness target")
    if k == "short_climax":
        return (f"climax at {t:.2f} s is cut short: it stays over the build ({d['build_lufs']:g} LUFS in the 3 s before) "
                f"for {d['held_s']:g} s, then falls {d['then_lu']:+g} LU; let it "
                "hold 3–5 s (held chords, ringing low notes, a cymbal swell) and settle over several seconds: a held climax "
                "carries the loudness target, so the build can start low")
    if k in ("late_climax", "early_climax"):
        side = "after" if k == "late_climax" else "before"
        fix = ("the music keeps growing well past the downbeat: hold the last bars before it a little lower and put the "
               "strongest attack on the downbeat; a bloom after it is normal, keep it" if side == "after" else
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
        return (f"near-mono mix: left/right correlation {d['correlation']:g} (wide mixes 0.4–0.8); give a mono source its own "
                "left and right: a `chorus` effect with spread 1, a `tremolo` with stereo above 0 (1 = auto-pan) or a stereo "
                "reverb; pan the mono parts apart; `width` cannot widen a mono recording")
    if k == "dull_top":
        return (f"dull top end: even the brightest tenth of the piece has its 4–16 kHz at {d['brightest_db']:g} dB "
                "against 250 Hz–1 kHz (benchmark: bright pop and lo-fi -2 to -9, orchestral and dark cues -13 to -19, dull mixes "
                "under -20); what brightens it: a bright part up an octave, higher velocity on recorded instruments (their "
                "loud layers are brighter), a cymbal, glockenspiel or bell at an audible level, less build-up of parts in "
                f"250 Hz–1 kHz; {shelf_fix(d)}")
    if k == "flat_top":
        return (f"top end did not grow into {t:.2f} s: 4–16 kHz against 250 Hz–1 kHz {d['start_db']:g} dB at the start "
                f"({d['start_s']:g} s) and {d['at_db']:g} dB from the moment ({d['grew_db']:+g} dB; builds that open up "
                "measure +11 to +15); what brightens it as it grows: add parts in register order (high ones last), raise "
                "recorded instruments' velocity through the build, a cymbal swell or high octave into the moment")
    if k == "squashed_hit":
        b = f" the 10 s before sit {d['build_under_lu']:g} LU under it, so" if d.get("build_under_lu") is not None else ""
        by = f" ({', '.join(d['drivers'])})" if d.get("drivers") else ""
        return (f"hit at {t:.2f} s squashed {d['reduced_db']:g} dB by the master limiter{by}:{b} the build carries the "
                "loudness target; let the hit ring or hold 3–6 s (a held chord, ringing low notes, a cymbal) and keep the "
                "build's peaks 4–6 dB under the ceiling (edit_loudness lift_quiet narrows the range: not the fix here)")
    return k


@remembered
def _whole(wav) -> list[dict]:
    y, sr = load(wav)
    out = lead_in.faults(y, sr) + [{"kind": "held_tone", "at_s": s["from_s"], "measured": {k: v for k, v in s.items() if k != "from_s"}}
           for s in held_spans(y, sr)]
    corr = _correlation(y)
    if corr is not None and corr > MONO_CORR:
        out.append({"kind": "near_mono", "at_s": 0.0, "measured": {"correlation": num(corr, 2)}})
    top = brightest(wav)
    if top is not None and top < DULL_DB:
        out.append({"kind": "dull_top", "at_s": 0.0, "measured": {"brightest_db": top,
                    "shelf": shelf_try.clearing(wav, DULL_DB + SHELF_MARGIN, SHELF_MOST_DB)}})
    return out


def check(wav, moments=None, limiter=None, whole=True, peaky=None, drums=None, song=None, data=None) -> dict:
    """The faults of `wav`: the asked-for `moments` ([{"at", "kind", "end"}], moments.KINDS; a {"kind": "tempo"} entry
    is checked by tempo_fit), and with `whole` the whole-piece ones (a silent start, a held tone, a near-mono mix, a hit
    the limiter squashed: `limiter` = listen.limiter's result). A soft stop names `peaky` to tame when the limiter's
    drivers are unknown. `drums`: a render's drum tracks' own files (a drop's gap is read on them). `song`: {"tracks":
    the render's track meters, "data": the document's data}, for a mix the limiter squashes (squash.py). `data` (else
    song's): the document's data, whose brief says what a hit's bars around it must leave (hit_room.py)."""
    timed = [m for m in moments or [] if m.get("kind") != "tempo"]
    found = moment_faults(wav, timed, drums) if timed else []
    found += hit_room.faults(wav, timed, data if data is not None else (song or {}).get("data")) if timed else []
    found = stop_soft.merge(found, limiter, peaky) + [f for m in moments or [] if m.get("kind") == "tempo" for f in tempo_fit.faults(m)]
    if whole:
        found += _whole(wav)
        if limiter:
            y, sr = load(wav)
            stops = [f["at_s"] for f in found if f["kind"] == "soft_stop"]     # a soft stop already names the limiter there
            hit = [f for f in _squashed(y, sr, limiter, [float(m["at"]) for m in timed if m.get("at") is not None])
                   if all(abs(f["at_s"] - s) > 1.0 for s in stops)]
            mix = squash.fault(wav, limiter, song)
            if hit and mix and mix[0]["measured"]["seconds_over"] < 3.0:
                mix = []                  # the limiter works only on the asked moment: squashed_hit says it
            found += hit + mix
    found = sorted(found, key=lambda f: f["at_s"])
    for f in found:
        f["words"] = _words(f)
    asked = f" (checked {len(moments)} asked moment{'s' * (len(moments) != 1)})" if moments else ""
    said = ("Faults: " + "; ".join(f["words"] for f in found) + ".") if found else f"No faults found{asked}."
    return {"faults": found, "words": said}
