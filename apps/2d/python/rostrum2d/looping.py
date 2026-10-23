"""How a run of pictures repeats (one rule for video layers and drawings): held at the end, looped, or ping-pong.
`fold` turns a position that may run past the end into a position inside the run."""
from __future__ import annotations

MODES = ["off", "loop", "pingpong"]
WORDS = {"off": "Off", "loop": "Loop", "pingpong": "Ping-pong"}


def mode_of(value) -> str:
    """A layer's Loop value as a mode: a video's older on/off switch (True = loop) or a mode's name."""
    if value in MODES:
        return value
    return "loop" if value is True else "off"


def fold(i: int, count: int, mode: str) -> int:
    """The place in 0..count-1 that place `i` (maybe past either end) shows: held at the ends (off), wrapped (loop) or
    bounced there and back with each end shown once (pingpong)."""
    if mode == "loop":
        return i % count
    if mode == "pingpong" and count > 1:
        k = i % (2 * count - 2)
        return k if k < count else 2 * count - 2 - k
    return min(max(i, 0), count - 1)
