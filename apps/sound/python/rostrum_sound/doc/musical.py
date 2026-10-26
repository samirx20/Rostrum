"""Musical times as people read them, like Logic: the one formatter and parser every field, readout and agent report
uses (never one per panel).

A position is bars.beats, both counted from 1 ("5.3": bar 5, its third count), or bars.beats.sixteenth where it falls
between counts ("5.3.2": the second sixteenth of it); never ticks on screen. A length is words ("1 beat",
"2 bars 1 beat"), or a note value ("1/8") when it is one, measured in the time signature where it starts. Typing also takes
the old forms: "5.3.480" (ticks), a length as "2.1". Counts are the time signature's own (eighths in 6/8); bars and seconds follow
the bar map and the tempo map, so time signature changes, tempo changes and glides are all read (`meter.py`,
`tempo.py`). Typing takes either form: "5", "5.3", "5.3.240" (bars.beats; a bare number is a bar), or seconds
with their unit or as a clock ("9.6 s", "0:09.6").
"""
from __future__ import annotations

import math
import re

from . import meter, tempo

TICKS = 960                    # ticks in one count (typed old form only: never shown)
DIVS = 4                       # sixteenths in one count: the finest the screen shows
_EPS = 1e-6
_MUSIC = re.compile(r"^\s*(\d+)(?:\.(\d+)(?:\.(\d+))?)?\s*$")
_SECS = re.compile(r"^\s*(?:(\d+):(\d+(?:\.\d*)?)|(\d+(?:\.\d*)?|\.\d+)\s*(?:s|sec|secs|seconds?))\s*$")
_WORDS = re.compile(r"^\s*(?:(\d+)\s*bars?)?[\s,]*(?:and\s+)?(?:(\d+(?:\.\d+)?)\s*beats?)?[\s,]*(?:and\s+)?(?:(\d+)\s*(?:sixteenths?|16ths?))?\s*$", re.I)
_FRACTION = re.compile(r"^\s*(dotted\s+)?1/(\d+)\s*$", re.I)
NOTE_LENGTHS = {1 / 32: "1/32", 3 / 64: "dotted 1/32", 1 / 16: "1/16", 3 / 32: "dotted 1/16", 1 / 8: "1/8", 3 / 16: "dotted 1/8",
                1 / 4: "1/4", 3 / 8: "dotted 1/4", 1 / 2: "1/2", 3 / 4: "dotted 1/2"}   # fractions of a whole note
# (a whole note is said as bars and beats: "1 bar" in 4/4, never "1/1"; "1/1" is still read back)
NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _parts(counts: float) -> tuple[int, int]:
    """(whole counts, sixteenths into the next count) of a count amount, to the nearest sixteenth."""
    return divmod(round(counts * DIVS), DIVS)


def position(sec: float, root: dict) -> str:
    """Seconds as bars.beats ("5.3"), with .sixteenth (1-4) when it falls between counts ("5.3.2")."""
    beat = tempo.beat_at(root, max(0.0, float(sec)))
    seg = meter.seg_at(root, beat)
    whole, div = _parts((beat - seg.start) / meter.count(seg))
    bars, n = divmod(whole, seg.per)
    return f"{seg.bars + bars + 1}.{n + 1}" + (f".{div + 1}" if div else "")


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def length(secs: float, root: dict, start: float = 0.0) -> str:
    """A length starting at `start` seconds in words: "1 beat", "2 bars 1 beat", "1 beat 2 sixteenths" (counted in
    the starting time signature). `parse` takes these back, and the old "2.1" form."""
    b0 = tempo.beat_at(root, max(0.0, float(start)))
    b1 = tempo.beat_at(root, max(0.0, float(start) + max(0.0, float(secs))))
    seg = meter.seg_at(root, b0)
    whole, div = _parts((b1 - b0) / meter.count(seg))
    bars, n = divmod(whole, seg.per)
    parts = ([_plural(bars, "bar")] if bars else []) + ([_plural(n, "beat")] if n else []) + ([_plural(div, "sixteenth")] if div else [])
    return " ".join(parts) or "0 beats"


def note_length(secs: float, root: dict, start: float = 0.0) -> str:
    """A note's length in note values ("1/8", "dotted 1/4") when it is one to the tick; otherwise `length`'s words.
    `parse` takes these back."""
    b0 = tempo.beat_at(root, max(0.0, float(start)))
    whole = (tempo.beat_at(root, max(0.0, float(start) + max(0.0, float(secs)))) - b0) / 4      # a beat is a quarter note
    for frac, name in NOTE_LENGTHS.items():
        if abs(whole - frac) * 4 * TICKS < 0.5:
            return name
    return length(secs, root, start)


def _fine(third, is_length: bool) -> float:
    """The third number as counts: a sixteenth (position 1-4, length 0-3) or, from five (length four) up, the old ticks."""
    if third is None:
        return 0.0
    n = int(third)
    if is_length and n < DIVS or not is_length and 1 <= n <= DIVS:
        return (n if is_length else n - 1) / DIVS
    if n >= TICKS:
        raise ValueError(f"Type the part of a beat as a sixteenth (1-{DIVS}), not {n}")
    return n / TICKS


def _music_beat(m, root: dict, is_length: bool, start_beat: float) -> float:
    bar, cnt, fine = int(m.group(1)), int(m.group(2) or (0 if is_length else 1)), _fine(m.group(3), is_length)
    if is_length:
        seg = meter.seg_at(root, start_beat)
        _count_in_bar(cnt, seg.per, 0)
        return start_beat + (bar * seg.per + cnt + fine) * meter.count(seg)
    if bar < 1 or cnt < 1:
        raise ValueError("bars and beats count from 1")
    b = meter.bar_start(root, bar)
    seg = meter.seg_at(root, b)
    _count_in_bar(cnt, seg.per, 1, bar)
    return b + (cnt - 1 + fine) * meter.count(seg)


def _count_in_bar(cnt: int, per: int, first: int, bar: int | None = None) -> None:
    """Refuse a count the bar does not have (5.9 in 4/4), saying how many it has."""
    if cnt > per - 1 + first:
        where = f"Bar {bar} has" if bar else "A bar has"
        raise ValueError(f"{where} {per} beats: {cnt} is not one of them" if first else
                         f"A bar has {per} beats, so a length counts 0–{per - 1} beats after the bars: {cnt} is too many")


def parse(text: str, root: dict, is_length: bool = False, start: float = 0.0) -> float:
    """Typed words as seconds (a length: seconds long from `start`). Raises ValueError, naming the forms, when they
    are neither."""
    s = str(text).strip()
    f = _FRACTION.match(s) if is_length else None
    if f and int(f.group(2)):                       # a note value: "1/8", "dotted 1/4"
        b0 = tempo.beat_at(root, max(0.0, float(start)))
        quarters = 4 / int(f.group(2)) * (1.5 if f.group(1) else 1)
        return tempo.seconds_at(root, b0 + quarters) - tempo.seconds_at(root, b0)
    w = _WORDS.match(s) if is_length and s and any(c.isalpha() for c in s) else None
    if w and any(w.groups()):                       # "2 bars 1 beat", "1 beat 2 sixteenths"
        b0 = tempo.beat_at(root, max(0.0, float(start)))
        seg = meter.seg_at(root, b0)
        counts = int(w.group(1) or 0) * seg.per + float(w.group(2) or 0) + int(w.group(3) or 0) / DIVS
        return tempo.seconds_at(root, b0 + counts * meter.count(seg)) - tempo.seconds_at(root, b0)
    m = _MUSIC.match(s)
    if m:
        b0 = tempo.beat_at(root, max(0.0, float(start)))
        b = _music_beat(m, root, is_length, b0)
        return tempo.seconds_at(root, b) - (tempo.seconds_at(root, b0) if is_length else 0.0)
    m = _SECS.match(s.replace(",", "."))
    if m:
        return float(m.group(1)) * 60 + float(m.group(2)) if m.group(1) else float(m.group(3))
    raise ValueError(f'"{text}" is not a time: type bars.beats ("5.3"), bars.beats.sixteenth ("5.3.2"), a length in words ("2 bars 1 beat") or a note value ("1/8"), or seconds ("9.6 s")')


def clock(sec: float) -> str:
    """Seconds as a clock: 0:09.60."""
    m, s = divmod(max(0.0, float(sec)), 60)
    return f"{int(m)}:{s:05.2f}"


def note_name(pitch) -> str:
    """A MIDI number as a note name (67 → "G4"); a name stays as it is; a chord joins with spaces."""
    if isinstance(pitch, list):
        return " ".join(note_name(p) for p in pitch)
    if isinstance(pitch, str) or isinstance(pitch, bool):
        return str(pitch)
    n = int(round(pitch))
    return f"{NOTES[n % 12]}{n // 12 - 1}"


def semitones(v: float) -> str:
    """A bend or shift with its unit: "+2 semitones", "−0.5 semitones", "0 semitones"."""
    v = round(float(v), 2)
    if math.isclose(v, 0, abs_tol=_EPS):
        return "0 semitones"
    txt = f"{abs(v):g}"
    return ("+" if v > 0 else "−") + txt + (" semitone" if abs(v) == 1 else " semitones")
