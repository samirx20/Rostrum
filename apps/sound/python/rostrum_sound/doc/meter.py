"""The bar map: the one place beats and bars turn into each other.

The song starts at the document's `beatsPerBar`; each time signature change (`meters[]`, type "meter":
{at, beatsPerBar}) sets a new bar length from its time on, held until the next change, and starts a new bar
there (a change between bar lines cuts the bar before it short). Like a tempo change it sits at a beat
(`{"beat": 32}`, the usual way) or at seconds, never on a marker. Bars, the ruler, the grid, the metronome's
accents, bar quantise and `bar(n)` all read this map.
"""
from __future__ import annotations

from . import tempo


def start_per_bar(root: dict) -> int:
    return int(root.get("beatsPerBar", 4))


def segments(root: dict) -> list[tuple[float, int, int]]:
    """(start beat, beats per bar, bars before it) per stretch of one time signature, the first at beat 0."""
    def beat_of(c):
        at = c["at"]
        return float(at["beat"]) if isinstance(at, dict) else tempo.beat_at(root, float(at))
    segs = [(0.0, start_per_bar(root), 0)]
    for b, c in sorted(((beat_of(c), c) for c in root.get("meters", []) if "at" in c and "beatsPerBar" in c),
                       key=lambda x: x[0]):
        lb, lper, lbars = segs[-1]
        per = int(c["beatsPerBar"])
        if b <= lb + 1e-9:                     # on the same beat as the one before (or beat 0): it replaces it
            segs[-1] = (lb, per, lbars)
            continue
        segs.append((b, per, lbars + int(-(-(b - lb - 1e-9) // lper))))
    return segs


def _seg_at(root: dict, beat: float):
    return next(s for s in reversed(segments(root)) if s[0] <= beat + 1e-9)


def per_bar_at(root: dict, beat: float) -> int:
    """The beats per bar playing at `beat`."""
    return _seg_at(root, beat)[1]


def bar_at(root: dict, beat: float) -> float:
    """Bars since the start (0 = the first bar's downbeat; 2.5 = halfway through the third bar)."""
    b0, per, bars = _seg_at(root, beat)
    return bars + (beat - b0) / per


def bar_start(root: dict, bar: int) -> float:
    """The beat bar `bar` starts on (bars counted from 1, as the ruler shows them)."""
    n = bar - 1
    b0, per, bars = next(s for s in reversed(segments(root)) if s[2] <= n)
    return b0 + (n - bars) * per


def bar_beats(root: dict, end_beat: float) -> list[float]:
    """The beat every bar starts on, from 0 to `end_beat`: the ruler, the grid and the metronome's accents."""
    out, segs = [], segments(root)
    for i, (b0, per, _) in enumerate(segs):
        stop = segs[i + 1][0] if i + 1 < len(segs) else float("inf")      # end_beat itself counts, as in beats()
        b = b0
        while b < stop - 1e-9 and b <= end_beat + 1e-9:
            out.append(round(b, 6))
            b += per
    return out


def bar_seconds(root: dict, end: float) -> list[float]:
    """The time every bar starts, from 0 to `end` seconds."""
    return [round(tempo.seconds_at(root, b), 6) for b in bar_beats(root, tempo.beat_at(root, end))]


def bar_length_beats(root: dict, beat: float) -> float:
    """How many beats the bar holding `beat` lasts (a bar cut short by a change counts what it has)."""
    b0, per, bars = _seg_at(root, beat)
    start = b0 + int((beat - b0 + 1e-9) // per) * per
    nxt = [s[0] for s in segments(root) if s[0] > start + 1e-9]
    return min(per, nxt[0] - start) if nxt else per


def snap(root: dict, beat: float, step: float | None) -> float:
    """`beat` to the nearest grid step counted from the bar it falls in (so the grid stays on the bar lines after
    an odd bar), or to the nearest bar line when `step` is None (the "bar" grid). Quantise and drags share this."""
    if step is None:
        lines = bar_beats(root, beat + 2 * per_bar_at(root, beat))
        return min(lines, key=lambda b: abs(b - beat))
    b0, per, _ = _seg_at(root, beat)
    start = b0 + int((beat - b0 + 1e-9) // per) * per
    return start + round((beat - start) / step) * step
