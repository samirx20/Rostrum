"""The written song as text, bar by bar, the way musicians read it: the chord symbol(s) per bar and each one-line
part's notes as names with octave and beat ("E4@1 G4@2.5"). Read from the document's notes (ears/written.py),
observations only.

The chord is named per beat from the chord parts (harmony.split_parts: tracks that play chords, plus a bass well
under them; with no chord track, every pitched track) and merged while it stays the same: "Cmaj7" for a whole bar,
"C@1 G/B@3" when it changes. "N.C." = nothing pitched sounds on that beat; "(D)" = one note only; "(C D Eb)" = notes
no chord shape fits. Every one-line track (melody, bass, counter-line) gets its notes; a chord part's notes are in
the chord line and the picture. A note held over the bar line shows as "~E4" at the next bar's start.
"""
from __future__ import annotations

import math
from bisect import bisect_left

from ..doc import keys, meter, tempo
from .harmony import _sounding, plays_chords, split_parts, windows
from .theory import name_chord

ALL_UP_TO = 32        # songs this long show every bar by default; longer ones the first DEFAULT_BARS
DEFAULT_BARS = 16


SNAP = 0.06          # a note this close (in beats) to a 16th or a triplet is shown on it: played timing reads as written


def _beat_text(x: float) -> str:
    return f"{round(x, 2):g}"


def position(root: dict, sec: float) -> tuple[int, float]:
    """(bar counted from 1, count in the bar from 1) of a time in seconds, as the ruler shows them; a count within SNAP
    of a 16th or a triplet is shown on it (a note played a hair before the bar line counts as the next bar's 1)."""
    beat = tempo.beat_at(root, sec)
    bar = meter.bar_at(root, beat)
    per = meter.per_bar_at(root, beat)
    n = math.floor(bar + 1e-9)
    count = (bar - n) * per + 1
    near = min((round(count * g) / g for g in (4, 3)), key=lambda c: abs(c - count))
    if abs(near - count) <= SNAP:
        count = near
    if count >= per + 1 - 1e-9:
        n, count = n + 1, 1.0
    return n + 1, count


def chord_label(upper: list[int], bass: int | None, key: str | None) -> str:
    """The chord symbol for the chord part's notes over the bass note (None: no bass part). The bass names the
    inversion when it fits the chord; when it doesn't, the chord is named from the chord part alone."""
    if not upper:
        return "N.C." if bass is None else f"({keys.pc_name(bass % 12, key)})"
    if bass is not None and bass < min(upper):
        name = name_chord(upper + [bass], bass, key)
        if name:
            return name
    pcs = sorted({m % 12 for m in upper}, key=lambda p: min(m for m in upper if m % 12 == p))
    if len(pcs) == 1:
        return f"({keys.pc_name(pcs[0], key)})"
    return name_chord(upper, min(upper), key) or "(" + " ".join(keys.pc_name(p, key) for p in pcs) + ")"


def bar_range(count: int, first: int | None, last: int | None) -> tuple[int, int]:
    """The bars shown: as asked (clipped to the song), else every bar up to ALL_UP_TO, else the first DEFAULT_BARS."""
    if count <= 0:
        return 1, 0
    if first is None and last is None:
        return 1, count if count <= ALL_UP_TO else DEFAULT_BARS
    a = max(1, int(first or 1))
    b = min(count, int(last if last is not None else a + DEFAULT_BARS - 1))
    return a, max(a - 1, b)


class _Span:
    """The notes sounding in a window, found by bisecting on start (a long song stays fast)."""

    def __init__(self, notes):
        self.notes = sorted(notes, key=lambda n: n["start"])
        self.starts = [n["start"] for n in self.notes]
        self.longest = max((n["end"] - n["start"] for n in self.notes), default=0.0)

    def sounding(self, s: float, e: float) -> list[int]:
        lo, hi = bisect_left(self.starts, s - self.longest - 1e-9), bisect_left(self.starts, e)
        return _sounding(self.notes[lo:hi], s, e)


def read(root: dict, notes: list[dict], end: float, first: int | None = None, last: int | None = None) -> dict:
    """{"from", "to", "of", "chord_tracks", "line_tracks", "chords": [[start_s, end_s, label]] (shown bars, merged),
    "rows": [{"bar", "chord", "parts": {track: text}}]}. `notes` as ears.written.written_notes (pitched, unmuted).

    The chord is read per beat from the chord parts and holds through rests shorter than a bar (a stab rings on the
    chart); a new one starts when the chord part's pitch classes change. The bass part (a one-line track well under
    them) names the inversion at the chord's first beat. With no chord part, every pitched track makes the chord."""
    count = meter.bar_count(root, end)
    a, b = bar_range(count, first, last)
    by: dict = {}
    for n in notes:
        by.setdefault(n["track"], []).append(n)
    order = list(dict.fromkeys(n["track"] for n in notes))
    chord_notes, _ = split_parts(notes)
    chord_tracks = [t for t in order if plays_chords(by[t])]
    named_from = list(dict.fromkeys(n["track"] for n in chord_notes))
    line_tracks = [t for t in order if t not in chord_tracks]
    upper = _Span([n for n in chord_notes if not chord_tracks or n["track"] in chord_tracks])
    bass = _Span([n for n in chord_notes if chord_tracks and n["track"] not in chord_tracks])
    key_at = lambda s: keys.key_for(root, s)

    wins = [w for w in windows(root, end, "beat") if w[2] <= b + 1]     # one bar past: is a rest at the end short?
    ups = [upper.sounding(s, e) for s, e, _, _ in wins]
    carry = [False] * len(wins)                 # a rest shorter than a bar, with the chord part playing after it
    k = 0
    while k < len(wins):
        if ups[k]:
            k += 1
            continue
        g = k
        while g < len(wins) and not ups[g]:
            g += 1
        if 0 < k and g < len(wins) and g - k < meter.per_bar_at(root, tempo.beat_at(root, wins[k][0])):
            carry[k:g] = [True] * (g - k)
        k = g
    beats: dict[int, list] = {}                  # bar -> [[start_s, end_s, beat, label]]
    held, cur = None, "N.C."                     # held: (pitch classes, notes) of the chord in force
    for (s, e, bar, beat), up, kept in zip(wins, ups, carry):
        pcs = frozenset(m % 12 for m in up)
        if up and (held is None or held[0] != pcs):
            held = (pcs, up)
        elif not up and not kept:
            held = None
        if up and held[1] is up or beat == 1 or held is None:
            lo = bass.sounding(s, e)
            cur = chord_label(held[1] if held else [], min(lo) if lo else None, key_at(s))
        if a <= bar <= b:
            beats.setdefault(bar, []).append([s, e, beat, cur])
    pos = {id(n): position(root, n["start"]) for t in line_tracks for n in by[t]}
    chords, rows = [], []
    for bar in range(a, b + 1):
        runs: list[list] = []
        for w in beats.get(bar, []):
            if runs and runs[-1][3] == w[3]:
                runs[-1][1] = w[1]
            else:
                runs.append(list(w))
        chords += [[r[0], r[1], r[3]] for r in runs]
        text = runs[0][3] if len(runs) == 1 else " ".join(f"{r[3]}@{r[2]}" for r in runs) if runs else "—"
        start_s = tempo.seconds_at(root, meter.bar_start(root, bar))
        parts = {}
        for t in line_tracks:
            words = []
            for n in by[t]:
                name = "+".join(keys.pitch_name(m, key_at(n["start"])) for m in n["midis"])
                nb, cnt = pos[id(n)]
                if nb == bar:
                    words.append(f"{name}@{_beat_text(cnt)}")
                elif nb < bar and n["end"] > start_s + 0.02:
                    words.append(f"~{name}")
            parts[t] = " ".join(words) or "—"
        rows.append({"bar": bar, "chord": text, "parts": parts})
    return {"from": a, "to": b, "of": count, "chord_tracks": named_from,
            "line_tracks": line_tracks, "chords": chords, "rows": rows}


def lines(bt: dict) -> list[str]:
    """One aligned line per bar: "  3 | Cmaj7       | lead E4@1 G4@2.5 | bass C2@1"."""
    rows = bt["rows"]
    if not rows:
        return []
    wb = len(str(rows[-1]["bar"]))
    wc = max(len(r["chord"]) for r in rows)
    wp = {t: max(len(r["parts"][t]) for r in rows) for t in bt["line_tracks"]}
    out = []
    for r in rows:
        cells = [f"{r['bar']:>{wb}}", f"{r['chord']:<{wc}}"] + [f"{t} {r['parts'][t]:<{wp[t]}}" for t in bt["line_tracks"]]
        out.append(" | ".join(cells).rstrip())
    return out


def header(bt: dict, kits: list[str], muted: list[str], other: list[str] = ()) -> str:
    """What the text shows and what it leaves out, so no part is dropped silently."""
    if bt["of"] == 0:
        return "No bars yet."
    shown = (f"bars {bt['from']}–{bt['to']} of {bt['of']}" + ("" if (bt["from"], bt["to"]) == (1, bt["of"]) else
             " (ask bars: 'from-to' for others)") if bt["to"] >= bt["from"] else f"no bars in that range (the song has {bt['of']})")
    out = [f"Bar by bar, {shown}. Chord per beat from {', '.join(bt['chord_tracks']) or 'nothing pitched'}"
           " (a chord holds through rests under a bar; N.C. = nothing pitched; (D) = one note; (C D Eb) = no chord shape)"]
    out.append(f"notes as name+octave@beat for {', '.join(bt['line_tracks'])} (beats to the nearest 16th or triplet; ~ = held over the bar line)" if bt["line_tracks"]
               else "no one-line parts")
    left = [t for t in bt["chord_tracks"] if t not in bt["line_tracks"]]
    if left:
        out.append(f"chord parts {', '.join(left)} are in the chord line, their voicings in the picture")
    if kits:
        out.append(f"drums ({', '.join(kits)}) in the picture only")
    if other:
        out.append(f"clips / voice lines ({', '.join(other)}) in the picture only")
    if muted:
        out.append(f"muted, left out: {', '.join(muted)}")
    return "; ".join(out) + "."
