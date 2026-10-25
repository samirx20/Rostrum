"""Times and pitches as the screen reads and writes them. No Qt.

Reading goes through the document's own `times` (seconds, `{"beat": n}`, `"#drop+0.5"`). Writing keeps the form
the item already used: a note placed in beats is moved in beats, one placed on a marker stays on that marker
(`"#drop+0.25"`), seconds stay seconds. A drag snaps to the grid unless it is free (Ctrl) or Snap is off.

A `Grid` is a window's grid setting (Grid ▾ and Snap in the arrangement's header; screen state, never saved): the
bridge holds one and passes it to every snap (drags, ends, the ruler's range, Draw, nudges); without one, the
default (Auto, Snap on) is used. Auto follows the zoom: the finest step at least MIN_PX wide on screen.

One snap, three ways (`snap(..., how=)`): a drag or a nudge goes to the NEAREST line; a click that makes something
(a Draw note, a drum hit, a double-click, an automation point) takes the CELL under the pointer, the line at or
before it; a time range's edges ("start" / "end") take a line within NEAR_PX, else the cell's start / end. `px` is
one screen pixel in seconds: the screen draws a line on its nearest whole pixel, so a pointer on that pixel is on
the line (a press exactly on a drawn line gives that line's time, a pixel before it the cell before).
"""
from __future__ import annotations

from rostrum_sound.doc import keys as K
from rostrum_sound.doc import meter, tempo, times
from rostrum_sound.doc.shift import spb, write_like

SNAP_BEATS = 0.25          # the music map's own snap (tempo / key changes, sections): a quarter beat
MIN_PX = 8.0               # Auto: no step narrower than this on screen
NEAR_PX = 3.0              # a range edge this close to a line takes the line
EPS = 1e-6                 # beats: a time written as a line's seconds is on that line


class Grid:
    """Grid ▾: "bar", "1/2", "beat" (1/4), "1/8", "1/16", "1/32", "1/8T", "1/16T" (triplets) or "auto" (follows the zoom);
    Snap on / off."""
    STEPS = {"1/2": 2.0, "beat": 1.0, "1/8": 0.5, "1/16": 0.25, "1/32": 0.125, "1/8T": 1 / 3, "1/16T": 1 / 6}
    CHOICES = ["auto", "bar", "1/2", "beat", "1/8", "1/16", "1/32", "1/8T", "1/16T"]

    def __init__(self):
        self.value, self.on, self.auto_beats = "auto", True, 0.25

    def beats(self, root: dict, at: float = 0.0) -> float:
        """One step in beats at beat `at`; for "bar", that bar's length (`snap` follows each bar's own); "beat" is
        the time signature's count there (an eighth in 6/8)."""
        if self.value == "bar":
            return meter.seg_at(root, at).bar
        if self.value == "beat":
            return meter.count(meter.seg_at(root, at))
        return self.auto_beats if self.value == "auto" else self.STEPS[self.value]

    def follow_zoom(self, span_beats: float, width_px: float, min_px: float = MIN_PX) -> bool:
        """Auto: the finest step at least `min_px` wide when `span_beats` fill `width_px` (1/32 … 4 beats). True when
        it changed."""
        px_per_beat = width_px / max(span_beats, 1e-6)
        b = next((b for b in (0.125, 0.25, 0.5, 1.0, 2.0) if b * px_per_beat >= min_px), 4.0)
        changed, self.auto_beats = b != self.auto_beats, b
        return changed


DEFAULT = Grid()             # never changed: what a caller without a window's grid gets


def step_beats(root: dict, grid: Grid | None = None) -> float:
    """One grid step in beats (nudges, Draw's note length, Ctrl+arrows)."""
    return (grid or DEFAULT).beats(root)


def sec(value, root: dict, where="time") -> float:
    return times.seconds(value, root, where)


def length_sec(value, root: dict, start: float = 0.0, item: dict | None = None) -> float:
    """A length as seconds for a thing starting at `start` seconds (beats through the tempo map; a tied note's
    `"next"` needs the note itself)."""
    return times.length_seconds(value, root, start, item)


def beat(t: float, root: dict) -> float:
    """The beat at `t` seconds (the tempo map)."""
    return tempo.beat_at(root, t)


def lines_around(t: float, root: dict, grid: Grid | None = None) -> tuple[float, float]:
    """(the grid line at or before `t`, the next one), in seconds. Steps count from the bar `t` is in, so the grid
    stays on the bar lines after an odd bar; a bar's last cell ends on the next bar line."""
    grid = grid or DEFAULT
    b = max(0.0, tempo.beat_at(root, max(0.0, t)))
    s = meter.seg_at(root, b)
    bar0 = s.start + ((b - s.start + EPS) // s.bar) * s.bar
    step = s.bar if grid.value == "bar" else grid.beats(root, b)
    lo = bar0 + ((b - bar0 + EPS) // step) * step
    hi = min(lo + step, bar0 + s.bar)
    return tempo.seconds_at(root, lo), tempo.seconds_at(root, hi)


def snap(t: float, root: dict, free: bool, grid: Grid | None = None, how: str = "nearest", px: float = 0.0) -> float:
    """`t` seconds onto `grid` (the window's; through the tempo map), unless free or its Snap is off. `how`:
    "nearest" (drags, ends, nudges), "cell" (a click that makes something: the cell under the pointer), "start" /
    "end" (a time range's edges). `px`: one screen pixel in seconds (0: not from the screen)."""
    grid = grid or DEFAULT
    if free or not grid.on:
        return max(0.0, round(t, 4))
    if how == "nearest":
        lo, hi = lines_around(t, root, grid)
        at = hi if hi - t < t - lo else lo
    else:
        lo, hi = lines_around(t + px / 2, root, grid)        # the pointer's pixel holds the line drawn on it
        near = min(NEAR_PX * px, (hi - lo) / 3)                 # (never so far that a small cell is skipped)
        if how == "start":
            at = hi if hi - t <= near else lo
        elif how == "end":
            at = lo if t - lo <= near else hi
        else:
            at = lo
    return max(0.0, round(at, 6))


write_time = write_like   # `t` seconds in the form `old` was written in (doc/shift.py)


def write_length(old, seconds: float, root: dict, start: float = 0.0):
    """`seconds` long from `start`, in the form `old` was written in."""
    if isinstance(old, dict) and "beats" in old:
        return {"beats": round(tempo.beat_at(root, start + seconds) - tempo.beat_at(root, start), 4)}
    return round(seconds, 4)


midi, name, keys = K.midi, K.pitch_name, K.midis      # pitches: the one place is doc/keys.py


def shift_pitch(p, semis: int):
    """Transpose by `semis`, keeping the form (names stay names, numbers stay numbers, chords stay chords)."""
    if isinstance(p, list):
        return [shift_pitch(x, semis) for x in p]
    k = min(127, max(0, midi(p) + semis))
    return k if isinstance(p, int) else name(k)
