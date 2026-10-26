"""Swing: what the document sets (each track's `perform.swing` on `swingGrid`) and what the audio plays.

The engine (engine/src/contract/perform.rs) moves a note on an odd cell of the swing grid later by swing × grid / 3
beats, so swing 1 puts the off-beat on the triplet. Heard swing reads that back on the same scale: 3 × (how much later
the off-beats land than the on-beats, as a fraction of the grid). Subtracting the on-beats' own lateness takes the
onset finder's delay and any lean out, so a straight part reads 0 and "swing set 0.55, heard 0.56" can be compared.
"""
from __future__ import annotations

import math

import numpy as np

from ..listen.core import num

MIN_ONSETS = 6                 # off-beats and on-beats each, for a reading
GRID_WORDS = {0.5: "8ths", 0.25: "16ths", 1.0: "beats", 0.125: "32nds"}


def grid_words(grid: float) -> str:
    return GRID_WORDS.get(grid, f"{grid:g}-beat cells")


def set_on(track: dict) -> tuple[float, float] | None:
    """(swing, grid) a track sets, or None (no swing; a perform of true / false / absent plays straight)."""
    p = track.get("perform")
    if isinstance(p, dict) and p.get("swing"):
        return float(p["swing"]), float(p.get("swingGrid", 0.5))
    return None


def words(track: dict) -> str:
    """'swing 0.55 on 8ths' or 'no swing (played straight)': inspect_item's feel line."""
    s = set_on(track)
    return f"swing {s[0]:g} on {grid_words(s[1])}" if s else "no swing (played straight)"


def for_source(root: dict, track: str | None) -> tuple[float, float, list[str]] | None:
    """The swing the audio should have: the picked track's, or for the mix the setting the most notes and hits carry
    (swing, grid, the tracks that set it); None when nothing swings."""
    tracks = [t for t in root.get("tracks", []) if track is None or t.get("id") == track]
    sets: dict = {}
    for t in tracks:
        if (s := set_on(t)) is not None:
            n, ids = sets.get(s, (0, []))
            sets[s] = (n + len(t.get("notes", [])) + len(t.get("hits", [])), ids + [t["id"]])
    if not sets:
        return None
    (swing, grid), (_, ids) = max(sets.items(), key=lambda kv: kv[1][0])
    return swing, grid, ids


def swung(beat: float, swing: float, grid: float) -> float:
    """Where a written beat position plays: moved later when it sits on an odd swing cell (the engine's rule)."""
    cell = beat / grid
    if swing > 0 and abs(cell - round(cell)) < 0.08 and round(cell) % 2:
        return beat + swing * grid / 3
    return beat


def heard(positions, grid: float) -> float | None:
    """The swing the onsets (fractional beats) play on `grid`, on the setting's scale; None with too few of either."""
    on, off = [], []
    for p in positions:
        c = p / grid
        n = math.floor(c + 0.4)                      # a swung off-beat lands up to 1/3 cell late: still its own cell
        d = c - n
        if -0.2 < d < 0.4:
            (off if n % 2 else on).append(d)
    if len(on) < MIN_ONSETS or len(off) < MIN_ONSETS:
        return None
    return num(max(0.0, 3 * (float(np.median(off)) - float(np.median(on)))), 2)


def line(want, got) -> str:
    """'swing set 0.55 on 8ths (drums), heard 0.56' / 'no swing set, heard 0.4 on 8ths'; '' when neither."""
    if want is None:
        return f"no swing set, but the off-beat 8ths land {got:g} swung" if got and got >= 0.15 else ""
    swing, grid, ids = want
    return (f"swing set {swing:g} on {grid_words(grid)} ({', '.join(ids)}), heard "
            + (f"{got:g}" if got is not None else "? (too few on- and off-beats to measure)"))
