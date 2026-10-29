"""stall: a build that goes flat in the bars just before its peak.

Round sound-ascent (Ascent: "begins quiet, builds steadily ... climax at exactly 38.0 s"): the rival rose about 1.7 LU
every bar into the climax (-18.7, -16.7, -15.3 LUFS over its last three bars); Rostrum's new r1 sat at -16.4, -15.0,
-16.3 (31-37 s flat, a judge heard it) and passed every check, since the climax checks read the downbeat and the 3 s
around it, never the bars leading in. So when the piece has a peak to build into (an asked climax, else the loudest
3 s when the brief asks for a build and no lift), the last BARS bars before it (the song's own bars; the last SKIP_S before
the peak is left out, so a breath before it, moment(...).rest(before=0.4), and rise_gap's gap fault do not count) are
read per bar: loudness (BS.1770 LUFS of the bar), density (notes and hits starting per beat, every track, from the
document) and brightness (the 2-8 kHz share of the bar). Loudness rising under STALL_LU across them, while density
rises under DENSER and brightness under BRIGHTER_DB, is a stall.

Calibrated on Ascent (last three bars, the last cut 0.5 s before 38.0 s): loudness rise rival +3.4, new r2 +2.0, old
r1 +1.7, new r1 +0.1, old r2 +0.1 LU; brightness rise rival +0.3, new r1 +2.3 (a cymbal swell over a flat band, heard
as noise), old r2 +3.1 dB. Brightness alone carries a build only past BRIGHTER_DB.

    measure(y, sr, data, peak_s) -> [{"bar", "from_s", "to_s", "lufs", "per_beat", "bright_db"}] (the last BARS bars)
    decide(rows) -> {"rise_lu", "denser_x", "brighter_db"} when the rows stall, else None
    fault(doc, wav, stems=None, moments=None) -> [shared fault "stall_before_peak"]
"""
from __future__ import annotations

import numpy as np
from rostrum_core.mcp import faults as shared

from .. import brief
from . import squash  # noqa: F401  registers big_build
from .bs1770 import integrated
from .core import load, num
from .part_read import played

BARS = 3             # the bars read before the peak (two steps of a build)
SKIP_S = 0.5         # the last half second before the peak is a breath, not the build
STALL_LU = 1.5       # a build rises at least this much over those bars (rival +3.4; stalled runs +0.1)
DENSER = 1.25        # ...or its notes per beat grow by this factor
BRIGHTER_DB = 4.0    # ...or its 2-8 kHz share by this much (a cymbal swell over a flat band measured +2.3)
QUIET_LUFS = -70.0
MIN_S = 0.4          # a bar window shorter than this (the peak just after a bar line) joins the bar before

brief.register("stall_before_peak", ["plateau", "plateaus", "levels off", "level off", "holds steady", "hold steady",
                                     "stays level", "no build", "steady state", "holds back", "hold back", "restrained"],
               "a plateau or a held level before the peak")


def _bright(seg, sr) -> float:
    m = np.asarray(seg, np.float64).reshape(len(seg), -1).mean(axis=1)
    s = np.abs(np.fft.rfft(m * np.hanning(len(m)))) ** 2
    f = np.fft.rfftfreq(len(m), 1 / sr)
    whole = float(s[f >= 50].sum())
    return 10 * np.log10(float(s[(f >= 2000) & (f < 8000)].sum()) / whole + 1e-12) if whole > 0 else -120.0


def windows(data, peak_s) -> list[tuple[int, float, float]]:
    """(bar number, from, to) for the last BARS bars before peak_s - SKIP_S (the last one cut there)."""
    from ..doc import meter
    cut = peak_s - SKIP_S
    starts = [s for s in meter.bar_seconds(data, cut) if s < cut]
    wins = [(i + 1, a, min(b, cut)) for i, (a, b) in enumerate(zip(starts, starts[1:] + [cut]))]
    if len(wins) > 1 and wins[-1][2] - wins[-1][1] < MIN_S:
        (n, a, _), (_, _, b) = wins[-2], wins[-1]
        wins = wins[:-2] + [(n, a, b)]
    return wins[-BARS:]


def starts(data) -> list[float]:
    """Every note and hit start in the song, unmuted tracks."""
    return sorted(p["at"] for t in data.get("tracks") or [] if not t.get("mute") for p in played(t, data))


def measure(y, sr, data, peak_s, onsets=None) -> list[dict]:
    from ..doc import tempo
    onsets = np.asarray(starts(data) if onsets is None else onsets, float)
    wins = windows(data, peak_s)
    # density over the same stretch of every bar (as long as the shortest, the last one cut before the peak): a cut
    # bar's downbeat notes over fewer beats would read as busier
    span = min((tempo.beat_at(data, b) - tempo.beat_at(data, a) for _, a, b in wins), default=1.0)
    rows = []
    for bar, a, b in wins:
        seg = y[int(a * sr):int(b * sr)]
        upto = tempo.seconds_at(data, tempo.beat_at(data, a) + span)
        rows.append({"bar": bar, "from_s": num(a, 2), "to_s": num(b, 2),
                     "lufs": num(max(QUIET_LUFS, integrated(seg, sr)), 1),
                     "per_beat": num(float(((onsets >= a - 1e-3) & (onsets < upto - 1e-3)).sum()) / max(span, 1e-6), 2),
                     "bright_db": num(_bright(seg, sr), 1)})
    return rows


def decide(rows) -> dict | None:
    """The stall over `rows` (first to last), or None when any of loudness, density or brightness rises enough."""
    if len(rows) < 2 or rows[-1]["lufs"] <= QUIET_LUFS:
        return None
    a, b = rows[0], rows[-1]
    rise = b["lufs"] - a["lufs"]
    denser = b["per_beat"] / a["per_beat"] if a["per_beat"] > 0 else (DENSER if b["per_beat"] > 0 else 1.0)
    brighter = b["bright_db"] - a["bright_db"]
    if rise >= STALL_LU or denser >= DENSER or brighter >= BRIGHTER_DB:
        return None
    return {"rise_lu": num(rise, 1), "denser_x": num(denser, 2), "brighter_db": num(brighter, 1)}


def peaks(data, y, sr, moments=None) -> list[tuple[float, str | None]]:
    """(seconds, marker name) of each peak a build leads into: the asked climaxes (`moments`, else the song's markers
    named for one), else the loudest 3 s when the brief asks for a build and asks no lift; [] when there is none. A lift
    is a sudden change (Morning Light: "clearly audible as a change, not a gradual fade"): the bars before it may hold."""
    from ..doc import markers
    from .weakest import kind_of
    marks = markers.all(data)
    if moments is None:
        kinds = [(t, n, kind_of(n)) for n, t in marks]
    else:
        kinds = [(float(m["at"]), next((n for n, s in marks if abs(s - float(m["at"])) <= 0.05), None), m.get("kind"))
                 for m in moments if m.get("at") is not None]
    asked = [(t, n) for t, n, k in kinds if k == "climax"]
    if asked:
        return sorted(asked)
    if any(k == "lift" for *_, k in kinds) or not brief.asks(data, "big_build"):
        return []
    from .loudness import loudest
    return [(float(loudest(y, sr)["short_term_3s"]["from_s"]), None)]


def _said(rows, key, unit) -> str:
    return ", ".join(f"{r[key]:g}" for r in rows) + unit


def words(rows, got, parts, peak_s, name) -> tuple[str, str, str]:
    """(what, fix, when) in plain words."""
    bars = f"bars {rows[0]['bar']}–{rows[-1]['bar']} ({rows[0]['from_s']:g}–{rows[-1]['to_s']:g} s)"
    into = f"the {'peak' if not name else repr(name)} at {peak_s:.2f} s"
    what = (f"the build stalls in {bars} before {into}: loudness {_said(rows, 'lufs', ' LUFS')} ({got['rise_lu']:+g} LU; a build "
            f"rises {STALL_LU:g} LU or more over these bars), notes per beat {_said(rows, 'per_beat', '')} (x{got['denser_x']:g}; "
            f"or x{DENSER:g} busier), 2–8 kHz share {_said(rows, 'bright_db', ' dB')} ({got['brighter_db']:+g} dB; or "
            f"{BRIGHTER_DB:g} dB brighter)")
    if parts:
        what += "; holding level there: " + ", ".join(
            f"{p['track']} ({p['rise_db']:+g} dB{' by its stem' if p['from'] == 'stem' else ' asked in the document'})" for p in parts)
    target = f"\"#{name}\"" if name else f"{peak_s:g}"
    ids = ", ".join(f"\"{p['track']}\"" for p in parts) or "<the parts playing there>"
    fix = (f"keep rising right up to the peak: lift {ids} across these bars with build_to({target}, over=..., parts=[{ids}]) "
           f"or each part's own t.shape(\"vol\", from_=0.4, to=1.0, over=(bar({rows[0]['bar']}), {target}), curve=\"late\") and "
           f"t.shape(\"bright\", ...) to open it up; add a part every bar or two into the peak (high ones last), or "
           f"play denser (8ths to 16ths, a roll); a breath just before the peak is fine (moment(...).rest(before=0.4)): "
           f"the last {SKIP_S:g} s is not read")
    return what, fix, bars


def fault(doc, wav, stems=None, moments=None) -> list[dict]:
    """[stall_before_peak] for each peak whose last BARS bars stall (none without a peak to build into)."""
    from ..doc import markers
    from .stall_parts import flat
    data = getattr(doc, "data", None) or {}
    if not wav or not data.get("tracks"):
        return []
    with markers.project(getattr(doc, "folder", None)):
        y, sr = load(wav)
        out, onsets = [], starts(data)
        for peak_s, name in peaks(data, y, sr, moments):
            rows = measure(y, sr, data, peak_s, onsets)
            got = decide(rows)
            if not got:
                continue
            parts = flat(data, rows, stems, STALL_LU, DENSER)
            what, fix, when = words(rows, got, parts, peak_s, name)
            fid = f"stall_before_peak:{name}" if name else f"stall_before_peak@{peak_s:g}"
            out.append(shared.fault(fid, what, fix, when))
        return out
