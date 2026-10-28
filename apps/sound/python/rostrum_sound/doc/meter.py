"""The bar map: the one place beats and bars turn into each other.

A song's beat (tempo, `{"beat": n}`, every length in beats) is always the quarter note. The song starts at the
document's `beatsPerBar` / `beatUnit` (4/4 unless set; 6/8 is six eighths); each time signature change (`meters[]`,
type "meter": {at, beatsPerBar, beatUnit}) sets a new bar from its time on, held until the next change, and starts
a new bar there; it must sit on a bar line of the bars before it (`off_bar`: a new change elsewhere is refused). A bar lasts beatsPerBar × 4 / beatUnit
beats: 3 in 6/8, 4.5 in 9/8; a beat unit left out is 4, so older songs read exactly as before. Like a tempo change
it sits at a beat (`{"beat": 32}`, the usual way) or at seconds, never on a marker. Bars, the ruler, the grid, the
metronome, quantise and `bar(n)` all read this map.

Counts are the time signature's own beats (eighths in 6/8): the grid's beat lines and the readout's bar.beat. Main
beats are what the click plays: in a compound bar (6/8, 9/8, 12/8) every third count, else every count.
"""
from __future__ import annotations

import math
from typing import NamedTuple

from . import tempo

UNITS = (2, 4, 8, 16)
EARLY = 0.125      # beats (a 1/32 note): the widest nudge Humanise / Feel give, a start this much before a line is on it
NUDGE = 0.03       # beats: a usual humanised nudge, within which a short figure's length is still its written one


class Seg(NamedTuple):
    start: float     # the beat it starts on
    bar: float       # one bar's length in beats
    bars: int        # bars before it
    per: int         # counts in a bar (the top number)
    unit: int        # what one count is (the bottom number)


def count(seg: Seg) -> float:
    """One count's length in beats (an eighth: 0.5)."""
    return 4 / seg.unit


def main_beats(seg: Seg) -> tuple[int, float]:
    """(main beats in a bar, each one's length in beats): 6/8 → (2, 1.5), 3/4 → (3, 1)."""
    if seg.unit >= 8 and seg.per > 3 and seg.per % 3 == 0:
        return seg.per // 3, 3 * count(seg)
    return seg.per, count(seg)


def _seg(start, per, unit, bars) -> Seg:
    return Seg(start, int(per) * 4 / int(unit), bars, int(per), int(unit))


def start_per_bar(root: dict) -> int:
    return int(root.get("beatsPerBar", 4))


def start_unit(root: dict) -> int:
    return int(root.get("beatUnit", 4))


def start_bar(root: dict) -> float:
    """The song's first bar's length in beats."""
    return start_per_bar(root) * 4 / start_unit(root)


def segments(root: dict) -> list[Seg]:
    """One per stretch of one time signature, the first at beat 0."""
    def beat_of(c):
        at = c["at"]
        return float(at["beat"]) if isinstance(at, dict) else tempo.beat_at(root, float(at))
    segs = [_seg(0.0, start_per_bar(root), start_unit(root), 0)]
    for b, c in sorted(((beat_of(c), c) for c in root.get("meters", []) if "at" in c and "beatsPerBar" in c),
                       key=lambda x: x[0]):
        last, unit = segs[-1], c.get("beatUnit", 4)
        if b <= last.start + 1e-9:             # on the same beat as the one before (or beat 0): it replaces it
            segs[-1] = _seg(last.start, c["beatsPerBar"], unit, last.bars)
            continue
        segs.append(_seg(b, c["beatsPerBar"], unit, last.bars + int(-(-(b - last.start - 1e-9) // last.bar))))
    return segs


def off_bar(root: dict, change: dict) -> str | None:
    """Why a time signature change is not on a bar line of the bars before it (None: it is). A change always starts a
    whole bar, as in every DAW: one between bar lines would leave a broken part-bar before it."""
    at = change.get("at")
    b = float(at["beat"]) if isinstance(at, dict) and "beat" in at else tempo.beat_at(root, float(at))
    before = seg_at({**root, "meters": [m for m in root.get("meters", []) if m.get("id") != change.get("id")]}, b)
    n = (b - before.start) / before.bar
    if abs(n - round(n)) * before.bar <= 1e-6:
        return None
    lo, hi = before.start + int(n) * before.bar, before.start + (int(n) + 1) * before.bar
    return (f'time signature change "{change.get("id")}" at beat {b:g} is not on a bar line: a change starts a new bar, '
            f'so put it at {{"beat": {lo:g}}} (bar {before.bars + int(n) + 1}) or {{"beat": {hi:g}}} (bar {before.bars + int(n) + 2})')


def seg_at(root: dict, beat: float) -> Seg:
    """The time signature playing at `beat`; before bar 1 (a pickup, song field gridStart) the first one reaches back,
    as the tempo map does, so a pickup's beats count as negative bars instead of failing."""
    segs = segments(root)
    return next((s for s in reversed(segs) if s.start <= beat + 1e-9), segs[0])


def per_bar_at(root: dict, beat: float) -> int:
    """The counts in the bar playing at `beat` (the top number)."""
    return seg_at(root, beat).per


def bar_at(root: dict, beat: float) -> float:
    """Bars since the start (0 = the first bar's downbeat; 2.5 = halfway through the third bar)."""
    s = seg_at(root, beat)
    return s.bars + (beat - s.start) / s.bar


def bars_long(root: dict, end: float) -> float:
    """How many bars a song ending at `end` seconds lasts (2.5 = two bars and half of the third): the one bar-count
    rule. Bar lines from `bar_seconds` include the closing line at the end, so their count is one more than this."""
    return bar_at(root, tempo.beat_at(root, max(0.0, float(end))))


def bar_count(root: dict, end: float) -> int:
    """The bars a song ending at `end` seconds touches: a bar only partly played counts as one."""
    n = bars_long(root, end)
    return max(0, int(n) + (n - int(n) > 1e-6))


def copy_step(root: dict, start: float, end: float, grid: float = 0.25, single: bool = False) -> float:
    """Beats from a figure to its copy (Ctrl+D, each step of Repeat): `start` / `end` in seconds, the first item's
    start and the last one's end (a drum hit takes one `grid` cell). Counted from the first start, never from the bar
    line before it, so a phrase from mid-bar lands right after itself, on the same beat (critic r11):
    - a figure longer than a beat: whole bars (four chords on bars 1–4 step 4 bars, a 2.5-bar phrase 3, two claps on
      beats 1 and 3 one bar);
    - a figure of a beat or less: the first of grid, 2 grids, … one beat that holds it (two 8ths step a beat, a hit
      one grid), so Ctrl+D builds a run;
    - one item longer than a beat: its own length rounded up to the grid.
    A humanised edge never adds a bar (up to EARLY) or a cell (up to NUDGE)."""
    b0 = tempo.beat_at(root, start)
    span = max(0.0, tempo.beat_at(root, end) - b0)
    grid = max(grid, 1 / 32)
    if span - NUDGE <= 1:
        step = grid
        while step < min(span - NUDGE, 1.0) - 1e-6:
            step *= 2
        return min(step, 1.0)
    if single:
        return math.ceil((span - NUDGE) / grid - 1e-6) * grid
    bar = seg_at(root, b0).bar
    return max(1, math.ceil((span - EARLY) / bar - 1e-6)) * bar


def bar_start(root: dict, bar: int) -> float:
    """The beat bar `bar` starts on (bars counted from 1, as the ruler shows them)."""
    n = bar - 1
    s = next(s for s in reversed(segments(root)) if s.bars <= n)
    return s.start + (n - s.bars) * s.bar


def _every(root: dict, end_beat: float, step) -> list[float]:
    """From each stretch's start, every `step(seg)` beats to its end (`end_beat` itself counts, as in beats())."""
    out, segs = [], segments(root)
    for i, s in enumerate(segs):
        stop = segs[i + 1].start if i + 1 < len(segs) else float("inf")
        d, k = step(s), 0
        while (b := s.start + k * d) < stop - 1e-9 and b <= end_beat + 1e-9:
            out.append(round(b, 6))
            k += 1
    return out


def bar_beats(root: dict, end_beat: float) -> list[float]:
    """The beat every bar starts on, from 0 to `end_beat`: the ruler, the grid and the metronome's accents."""
    return _every(root, end_beat, lambda s: s.bar)


def _seconds(root: dict, end: float, step) -> list[float]:
    return [round(tempo.seconds_at(root, b), 6) for b in _every(root, tempo.beat_at(root, end), step)]


def bar_seconds(root: dict, end: float) -> list[float]:
    """The time every bar starts, from 0 to `end` seconds."""
    return _seconds(root, end, lambda s: s.bar)


def count_seconds(root: dict, end: float) -> list[float]:
    """The time of every count (each eighth in 6/8, each quarter in 4/4), from 0 to `end`: the grid's beat lines."""
    return _seconds(root, end, count)


def click_seconds(root: dict, end: float) -> list[float]:
    """The time of every main beat, from 0 to `end`: where the metronome clicks (1 and 4 in 6/8)."""
    return _seconds(root, end, lambda s: main_beats(s)[1])


def plain(root: dict) -> bool:
    """Whether every main beat is the quarter note (x/4 throughout): the click then follows the tempo's beats."""
    return all(main_beats(s)[1] == 1.0 for s in segments(root))


def bar_length_beats(root: dict, beat: float) -> float:
    """How many beats the bar holding `beat` lasts (a bar cut short by a change counts what it has)."""
    s = seg_at(root, beat)
    start = s.start + int((beat - s.start + 1e-9) // s.bar) * s.bar
    nxt = [x.start for x in segments(root) if x.start > start + 1e-9]
    return min(s.bar, nxt[0] - start) if nxt else s.bar


def snap(root: dict, beat: float, step: float | None, swing: float = 0.0) -> float:
    """`beat` to the nearest grid step counted from the bar it falls in (so the grid stays on the bar lines after
    an odd bar), or to the nearest bar line when `step` is None (the "bar" grid). Quantise and drags share this.
    `swing` (0 … 1) moves every off-beat (odd) grid line late by swing × step / 3, the engine's swing (perform.rs):
    1 puts an off-beat 8th on the triplet."""
    if step is None:
        lines = bar_beats(root, beat + 2 * seg_at(root, beat).bar)
        return min(lines, key=lambda b: abs(b - beat))
    s = seg_at(root, beat)
    start = s.start + int((beat - s.start + 1e-9) // s.bar) * s.bar
    k = round((beat - start) / step)
    if not swing:
        return start + k * step
    lines = [start + j * step + (swing * step / 3 if j % 2 else 0.0) for j in (k - 1, k, k + 1)]
    return min(lines, key=lambda b: abs(b - beat))
