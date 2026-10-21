"""Times and pitches as the screen reads and writes them. No Qt.

Reading goes through the document's own `times` (seconds, `{"beat": n}`, `"#drop+0.5"`). Writing keeps the form
the item already used: a note placed in beats is moved in beats, one placed on a marker stays on that marker
(`"#drop+0.25"`), seconds stay seconds. A drag snaps to a quarter beat unless it is free (Shift).
"""
from __future__ import annotations

from rostrum_sound.doc import keys as K
from rostrum_sound.doc import tempo, times
from rostrum_sound.doc.shift import spb, write_like

SNAP_BEATS = 0.25


def sec(value, root: dict, where="time") -> float:
    return times.seconds(value, root, where)


def length_sec(value, root: dict, start: float = 0.0) -> float:
    """A length as seconds for a thing starting at `start` seconds (beats through the tempo map)."""
    return times.length_seconds(value, root, start)


def beat(t: float, root: dict) -> float:
    """The beat at `t` seconds (the tempo map)."""
    return tempo.beat_at(root, t)


def snap(t: float, root: dict, free: bool) -> float:
    """To the nearest quarter beat (through the tempo map), unless free."""
    if free:
        return max(0.0, round(t, 4))
    b = round(tempo.beat_at(root, t) / SNAP_BEATS) * SNAP_BEATS
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
