"""Times and pitches as the screen reads and writes them. No Qt.

Reading goes through the document's own `times` (seconds, `{"beat": n}`, `"#drop+0.5"`). Writing keeps the form
the item already used: a note placed in beats is moved in beats, one placed on a marker stays on that marker
(`"#drop+0.25"`), seconds stay seconds. A drag snaps to a quarter beat unless it is free (Shift).
"""
from __future__ import annotations

import re

from rostrum_sound.doc import times

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
STEPS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
NOTE = re.compile(r"^([A-Ga-g])(#|b)?(-?\d)$")
SNAP_BEATS = 0.25


def spb(root: dict) -> float:
    """Seconds per beat."""
    return 60.0 / times.bpm(root)


def sec(value, root: dict, where="time") -> float:
    return times.seconds(value, root, where)


def length_sec(value, root: dict) -> float:
    return times.length_seconds(value, root)


def snap(t: float, root: dict, free: bool) -> float:
    if free:
        return max(0.0, round(t, 4))
    step = SNAP_BEATS * spb(root)
    return max(0.0, round(round(t / step) * step, 6))


def write_time(old, t: float, root: dict):
    """`t` seconds in the form `old` was written in."""
    name = times.marker_ref(old)
    if name is not None:
        m = times.markers(root).get(name)
        if m is not None:
            off = round(t - times.seconds(m.get("at", 0), root, f"marker {name}"), 4)
            return f"#{name}" if abs(off) < 1e-6 else f"#{name}{off:+g}"
    if isinstance(old, dict) and "beat" in old:
        return {"beat": round(t / spb(root), 4)}
    return round(t, 4)


def write_length(old, seconds: float, root: dict):
    if isinstance(old, dict) and "beats" in old:
        return {"beats": round(seconds / spb(root), 4)}
    return round(seconds, 4)


def midi(p) -> int:
    """A pitch ("D4", "F#3", "Bb2", or a MIDI number) as a MIDI number (C4 = 60)."""
    if isinstance(p, int):
        return p
    m = NOTE.match(p)
    if m is None:
        raise ValueError(f"not a note: {p!r}")
    acc = {"#": 1, "b": -1}.get(m.group(2) or "", 0)
    return (int(m.group(3)) + 1) * 12 + STEPS[m.group(1).upper()] + acc


def name(k: int) -> str:
    return f"{NAMES[k % 12]}{k // 12 - 1}"


def keys(p) -> list[int]:
    """The MIDI numbers a note plays (a chord is a list)."""
    return [midi(x) for x in p] if isinstance(p, list) else [midi(p)]


def shift_pitch(p, semis: int):
    """Transpose by `semis`, keeping the form (names stay names, numbers stay numbers, chords stay chords)."""
    if isinstance(p, list):
        return [shift_pitch(x, semis) for x in p]
    k = min(127, max(0, midi(p) + semis))
    return k if isinstance(p, int) else name(k)
