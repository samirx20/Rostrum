"""hit_room: an asked hit that the bars around it bury, `buried_hit`: the bed after it as loud as the hit, or the
near silence the brief asks for after it never coming.

Round sound-endings, Vault ("one hard hit at exactly 31.5 s ... the loudest moment of the piece. After the hit: 2–3 s
of near silence or ringing tail, then an unresolved low drone to the end", about -16 LUFS): both Rostrum runs brought
the drone back loud right after the hit to reach the loudness target on a mostly quiet piece, and both judges heard
it ("the post-hit pad at 40.5 s is louder than the hit", "-23 dB at 35 s, not near silence"). The hit's attack checks
(weak_hit, squashed_hit) all passed: they read the hit's first ~21 ms and the limiter, never the bars after it.

Measured on every judged Vault file (results/<round>/bench/…/2-vault*.wav; K-weighted, ungated; the hit = its loudest
0.4 s from 0.2 s before to 1 s after the asked time):

- quiet after (QUIET_LU): the quietest 1 s within 0.5 to 4.5 s after the hit, under the hit. Judged good: Python+GM 34.2
  LU (7.5), sound-tighten r1 29.7 and r2 34.2 (both 7, "the deepest post-hit silence"). Judged bad: endings r1 12.4,
  r2 20.6, motion r1 25.4 (4.5), deliver-clean r1 2.4 ("the near-silence after the hit never comes"), 3e r1 22.9,
  gaps2 13.3. Passes at 27 or more. Only when the brief asks for quiet after the hit (brief kind quiet_after_hit).
- bed after (BED_LU): the loudest 1 s from 4 s after the hit to the end, under the hit. Good: 10.5, 8.4, 15.8. Bad:
  endings r1 5.8, r2 1.0, motion r1 4.5, 3e r1 4.6, deliver-clean r1 5.1. Passes at 7 or more when the brief asks for
  the hit to be the loudest moment or for quiet after it; otherwise at 0 (nothing after the hit louder than the hit).
- bars before (BEFORE_LU): the loudest 0.4 s up to 0.5 s before the hit, under the hit. Every judged file passes 2.6 or
  more (lowest: endings r2 2.6, gaps2 3.6, tighten r1 3.8), so 2 for a brief asking for the loudest moment, else 0.

A note, never a gate: it says what it measured and what would make the hit stand out. A loudness target does not excuse it: the target is the whole file's, and the hit carries it (fault_shape.loudness_fault
says so when the piece has an asked hit).

    measure(y, sr, at) -> {hit_lufs, quiet_under_lu, quiet_from_s, bed_under_lu, bed_from_s, before_under_lu, before_from_s}
    faults(wav, moments, data) -> [raw fault {kind "buried_hit", at_s, measured}]   (faults.py words it with words())
    guard_spans(data, moments) -> [(from_s, to_s)]: the asked quiet after each hit (fault_shape: the loudness note's words)
"""
from __future__ import annotations

import re

import numpy as np

from .. import brief
from . import bs1770
from .core import load, num

HIT_FROM_S, HIT_TO_S = -0.2, 1.0     # the hit's own loudest 0.4 s is found in this span around the asked time
QUIET_FROM_S, QUIET_TO_S = 0.5, 4.5  # the asked near silence or ringing tail: its quietest 1 s within this span after the hit
BED_FROM_S = 4.0                     # the bars after: from this long after the hit to the end
BEFORE_GAP_S = 0.5                   # the bars before: up to this long before the hit
QUIET_LU = 27.0
BED_LU, BED_ANY_LU = 7.0, 0.0
BEFORE_LU, BEFORE_ANY_LU = 2.0, 0.0
QUIET_LUFS = -70.0

_AFTER = re.compile(r"\b(?:silence|silent|quiet|nothing|ring|rings|ringing|tail|space|breath|hush)\b(?: \w+){0,3} after (?:the |it|that )?"
                    r"(?:hit|impact|stab|sting|it)\b|\bafter (?:the )?(?:hit|impact|stab)\b(?: \w+){0,4} "
                    r"(?:silence|silent|quiet|nothing|ring|rings|ringing|tail|space|breath)\b")
brief.register("quiet_after_hit", ["near silence", "nearly silent", "ringing tail", "silence after", "drops to silence",
                                   "drop to silence", _AFTER], "quiet after the hit")
brief.register("loudest_hit", ["loudest moment", "loudest point", "loudest part", "loudest hit", "the loudest"],
               "the hit as the loudest moment")

FIX = ("keep the bars after the hit quiet: let the hit hold its full level about 2–2.5 s (a held low chord, ringing "
       "timpani or piano) and fall into the quiet; stop the bed on the hit for the asked quiet (m = moment(\"hit\", "
       "at=...); m.stop(<the bed's tracks>, until=<the hit + 2.5 s>, release=0.3)); bring the drone back soft (velocity "
       "0.2–0.35, or a track.dynamics lane falling to 0.25 after the hit); never lift the quiet parts after the hit to "
       "reach the loudness target: the hit carries it (aim at the quiet end of the brief's loudness range instead)")


def _curve(kw_cs, sr, w, step=0.05):
    """(window start times, ungated K-weighted loudness of each `w`-second window) every `step` s."""
    n = int(w * sr)
    st = np.arange(0, max(1, len(kw_cs) - n), max(1, int(step * sr)))
    with np.errstate(divide="ignore"):
        lufs = -0.691 + 10 * np.log10((kw_cs[np.minimum(st + n, len(kw_cs) - 1)] - kw_cs[st]) / n + 1e-12)
    return st / sr, np.maximum(lufs, QUIET_LUFS)


def _pick(t, v, a, b, fn):
    k = (t >= a) & (t < b)
    if not k.any():
        return None, None
    i = np.flatnonzero(k)[fn(v[k])]
    return float(v[i]), float(t[i])


def measure(y, sr, at) -> dict | None:
    """The hit against the bars around it (None: nothing measurable at `at`)."""
    kw = bs1770.k_weight(y, sr)
    g = np.array(bs1770.GAINS[:kw.shape[1]])
    cs = np.concatenate([[0.0], np.cumsum((kw * kw) @ g)])
    dur = len(y) / sr
    t4, m4 = _curve(cs, sr, 0.4)
    t1, m1 = _curve(cs, sr, 1.0)
    hit, _ = _pick(t4, m4, at + HIT_FROM_S, at + HIT_TO_S, np.argmax)
    if hit is None or hit <= QUIET_LUFS:
        return None
    quiet, qt = _pick(t1, m1, at + QUIET_FROM_S, at + QUIET_TO_S - 1.0 + 1e-6, np.argmin)
    bed, bt = _pick(t1, m1, at + BED_FROM_S, dur - 1.0 + 1e-6, np.argmax)
    bef, ft = _pick(t4, m4, 0.0, at - BEFORE_GAP_S - 0.4 + 1e-6, np.argmax)
    under = lambda v: num(hit - v, 1) if v is not None else None   # noqa: E731
    return {"hit_lufs": num(hit, 1), "quiet_under_lu": under(quiet), "quiet_from_s": num(qt, 2) if qt is not None else None,
            "bed_under_lu": under(bed), "bed_from_s": num(bt, 2) if bt is not None else None,
            "before_under_lu": under(bef), "before_from_s": num(ft, 2) if ft is not None else None}


def needs(data) -> dict:
    """What the brief asks around a hit: {quiet: phrase or None, loudest: phrase or None, bed_lu, before_lu}."""
    quiet, loud = brief.asks(data, "quiet_after_hit"), brief.asks(data, "loudest_hit")
    strict = bool(quiet or loud)
    return {"quiet": quiet, "loudest": loud, "bed_lu": BED_LU if strict else BED_ANY_LU,
            "before_lu": BEFORE_LU if loud else BEFORE_ANY_LU}


def faults(wav, moments, data=None) -> list[dict]:
    """A buried_hit per asked hit whose bars around it break what passes (needs()); its `measured` names each failing
    reading in `short` (quiet, bed, before)."""
    hits = [float(mo["at"]) for mo in moments or [] if mo.get("kind", "hit") == "hit" and mo.get("at") is not None]
    if not hits:
        return []
    y, sr = load(wav)
    need, out = needs(data), []
    for at in hits:
        m = measure(y, sr, at)
        if not m:
            continue
        short = []
        if need["quiet"] and m["quiet_under_lu"] is not None and m["quiet_under_lu"] < QUIET_LU:
            short.append("quiet")
        if m["bed_under_lu"] is not None and m["bed_under_lu"] < need["bed_lu"]:
            short.append("bed")
        if m["before_under_lu"] is not None and m["before_under_lu"] < need["before_lu"]:
            short.append("before")
        if short:
            out.append({"kind": "buried_hit", "at_s": at, "measured": {**m, "short": short, "quiet_need_lu": QUIET_LU if need["quiet"] else None,
                        "bed_need_lu": need["bed_lu"], "before_need_lu": need["before_lu"], "asked": need["quiet"] or need["loudest"]}})
    return out


def words(f) -> str:
    """faults.py's words for a buried_hit: each failing reading with what passes, then FIX."""
    t, d = f["at_s"], f["measured"]
    bits = []
    if "quiet" in d["short"]:
        bits.append(f"the quiet after it is not quiet: its quietest 1 s from {t + QUIET_FROM_S:.1f} to {t + QUIET_TO_S:.1f} s "
                    f"(from {d['quiet_from_s']:g} s) sits only {d['quiet_under_lu']:g} LU under the hit; near silence or a "
                    f"ringing tail sits {QUIET_LU:g} LU or more under it")
    if "bed" in d["short"]:
        bits.append(f"the bars after it are as loud as the hit: the loudest 1 s from {t + BED_FROM_S:.1f} s (at "
                    f"{d['bed_from_s']:g} s) is {d['bed_under_lu']:g} LU under it; passes at {d['bed_need_lu']:g} LU or more")
    if "before" in d["short"]:
        bits.append(f"the bars before it reach it: the loudest 0.4 s before (at {d['before_from_s']:g} s) is "
                    f"{d['before_under_lu']:g} LU under it; passes at {d['before_need_lu']:g} LU or more")
    why = f" (the brief: \"{d['asked']}\")" if d.get("asked") else ""
    return f"hit at {t:.2f} s buried by the bars around it{why}, the hit {d['hit_lufs']:g} LUFS: {'; '.join(bits)}; fix: {FIX}"


def guard_spans(data, moments) -> list[tuple[float, float]]:
    """The asked quiet after each hit (when the brief asks for it): (hit + QUIET_FROM_S, hit + BED_FROM_S)."""
    if not brief.asks(data, "quiet_after_hit"):
        return []
    return [(float(mo["at"]) + QUIET_FROM_S, float(mo["at"]) + BED_FROM_S) for mo in moments or []
            if mo.get("kind", "hit") == "hit" and mo.get("at") is not None]
