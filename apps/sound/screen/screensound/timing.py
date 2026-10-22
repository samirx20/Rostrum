"""Times and pitches as the screen reads and writes them. No Qt.

Reading goes through the document's own `times` (seconds, `{"beat": n}`, `"#drop+0.5"`). Writing keeps the form
the item already used: a note placed in beats is moved in beats, one placed on a marker stays on that marker
(`"#drop+0.25"`), seconds stay seconds. A drag snaps to the grid unless it is free (Ctrl) or Snap is off.

A `Grid` is a window's grid setting (Grid ▾ and Snap in the arrangement's header; screen state, never saved): the
bridge holds one and passes it to every snap (drags, ends, the ruler's range, Draw, nudges); without one, the
default (1/16, Snap on) is used.
"""
from __future__ import annotations

from rostrum_sound.doc import keys as K
from rostrum_sound.doc import tempo, times
from rostrum_sound.doc.shift import spb, write_like

SNAP_BEATS = 0.25          # the music map's own snap (tempo / key changes, sections): a quarter beat


class Grid:
    """Grid ▾: "bar", "1/2", "beat" (1/4), "1/8", "1/16", "1/32", "1/8T", "1/16T" (triplets) or "auto" (follows the zoom);
    Snap on / off."""
    STEPS = {"1/2": 2.0, "beat": 1.0, "1/8": 0.5, "1/16": 0.25, "1/32": 0.125, "1/8T": 1 / 3, "1/16T": 1 / 6}
    CHOICES = ["auto", "bar", "1/2", "beat", "1/8", "1/16", "1/32", "1/8T", "1/16T"]

    def __init__(self):
        self.value, self.on, self.auto_beats = "1/16", True, 0.25

    def beats(self, root: dict) -> float:
        if self.value == "bar":
            return float(root.get("beatsPerBar", 4))
        return self.auto_beats if self.value == "auto" else self.STEPS[self.value]

    def follow_zoom(self, span_beats: float, width_px: float = 1200.0, min_px: float = 16.0):
        """Auto: the finest step at least `min_px` wide at this zoom (1/32 … 4 beats)."""
        for b in (0.125, 0.25, 0.5, 1.0, 2.0, 4.0):
            if b * width_px / max(span_beats, 1e-6) >= min_px:
                self.auto_beats = b
                return
        self.auto_beats = 4.0


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


def snap(t: float, root: dict, free: bool, grid: Grid | None = None) -> float:
    """To the nearest step of `grid` (the window's; through the tempo map), unless free or its Snap is off."""
    grid = grid or DEFAULT
    if free or not grid.on:
        return max(0.0, round(t, 4))
    step = grid.beats(root)
    b = round(tempo.beat_at(root, t) / step) * step
    return max(0.0, round(tempo.seconds_at(root, b), 6))


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
