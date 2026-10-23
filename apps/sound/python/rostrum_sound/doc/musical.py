"""Musical times as people read them, like Logic: the one formatter and parser every field, readout and agent report
uses (never one per panel).

A position is bars.beats, both counted from 1 ("5.3": bar 5, its third count), or bars.beats.ticks where it falls
between counts ("5.3.480"; TICKS a count). A length is counted from 0 ("0.2": two counts, "2.0": two bars), measured
in the time signature where it starts. Counts are the time signature's own (eighths in 6/8); bars and seconds follow
the bar map and the tempo map, so time signature changes, tempo changes and glides are all read (`meter.py`,
`tempo.py`). Typing takes either form: "5", "5.3", "5.3.240" (bars.beats; a bare number is a bar), or seconds
with their unit or as a clock ("9.6 s", "0:09.6").
"""
from __future__ import annotations

import math
import re

from . import meter, tempo

TICKS = 960                    # ticks in one count (Logic's resolution)
_EPS = 1e-6
_MUSIC = re.compile(r"^\s*(\d+)(?:\.(\d+)(?:\.(\d+))?)?\s*$")
_SECS = re.compile(r"^\s*(?:(\d+):(\d+(?:\.\d*)?)|(\d+(?:\.\d*)?|\.\d+)\s*(?:s|sec|secs|seconds?))\s*$")
NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _parts(counts: float) -> tuple[int, int]:
    """(whole counts, ticks) of a count amount, rounded to the tick."""
    t = round(counts * TICKS)
    return t // TICKS, t % TICKS


def _join(a: int, b: int, ticks: int, fine: bool) -> str:
    return f"{a}.{b}" + (f".{ticks}" if ticks or fine else "")


def position(sec: float, root: dict, fine: bool = False) -> str:
    """Seconds as bars.beats ("5.3"), with .ticks when it falls between counts or `fine` asks for them."""
    beat = tempo.beat_at(root, max(0.0, float(sec)))
    seg = meter.seg_at(root, beat)
    counts = (beat - seg.start) / meter.count(seg)
    whole, ticks = _parts(counts)
    bars, n = divmod(whole, seg.per)
    return _join(seg.bars + bars + 1, n + 1, ticks, fine)


def length(secs: float, root: dict, start: float = 0.0, fine: bool = False) -> str:
    """A length starting at `start` seconds as bars.beats counted from 0 ("0.2", "2.0"), in the starting time signature."""
    b0 = tempo.beat_at(root, max(0.0, float(start)))
    b1 = tempo.beat_at(root, max(0.0, float(start) + max(0.0, float(secs))))
    seg = meter.seg_at(root, b0)
    whole, ticks = _parts((b1 - b0) / meter.count(seg))
    bars, n = divmod(whole, seg.per)
    return _join(bars, n, ticks, fine)


def _music_beat(m, root: dict, is_length: bool, start_beat: float) -> float:
    bar, cnt, ticks = int(m.group(1)), int(m.group(2) or (0 if is_length else 1)), int(m.group(3) or 0)
    if ticks >= TICKS:
        raise ValueError(f"A count has {TICKS} ticks: type 0–{TICKS - 1} after the second dot")
    if is_length:
        seg = meter.seg_at(root, start_beat)
        _count_in_bar(cnt, seg.per, 0)
        return start_beat + (bar * seg.per + cnt + ticks / TICKS) * meter.count(seg)
    if bar < 1 or cnt < 1:
        raise ValueError("bars and beats count from 1")
    b = meter.bar_start(root, bar)
    seg = meter.seg_at(root, b)
    _count_in_bar(cnt, seg.per, 1, bar)
    return b + (cnt - 1 + ticks / TICKS) * meter.count(seg)


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
    m = _MUSIC.match(s)
    if m:
        b0 = tempo.beat_at(root, max(0.0, float(start)))
        b = _music_beat(m, root, is_length, b0)
        return tempo.seconds_at(root, b) - (tempo.seconds_at(root, b0) if is_length else 0.0)
    m = _SECS.match(s.replace(",", "."))
    if m:
        return float(m.group(1)) * 60 + float(m.group(2)) if m.group(1) else float(m.group(3))
    raise ValueError(f'"{text}" is not a time: type bars.beats ("5.3"), bars.beats.ticks ("5.3.480") or seconds ("9.6 s")')


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
    """A bend or shift with its unit: "+2 st", "−0.5 st", "0 st"."""
    v = round(float(v), 2)
    if math.isclose(v, 0, abs_tol=_EPS):
        return "0 st"
    txt = f"{abs(v):g}"
    return ("+" if v > 0 else "−") + txt + " st"
