"""A path's arithmetic, app-neutral: points sampled at times -> steps, speeds, the peak; stretches where something moves
(merged), the holds between them; sudden jumps (one step far bigger than both its neighbours). Facts only, no taste.
"""
from __future__ import annotations

import math

HOLD_MIN_S = 0.5          # a still stretch shorter than this isn't reported as a hold
JUMP_FACTOR = 4.0         # a step this many times bigger than both its neighbours is a jump


def r(x: float, n: int = 3) -> float:
    return round(float(x), n)


def steps(points: list) -> list[float]:
    """How far each sample is from the one before (len(points) - 1 numbers), in the points' own units."""
    return [math.dist(p, q) for p, q in zip(points, points[1:])]


def rates(points: list, times: list[float]) -> list[float]:
    """Speed over each step: its distance over its time."""
    return [d / (times[i + 1] - times[i]) for i, d in enumerate(steps(points))]


def peak(values: list[float]) -> int:
    """The index of the biggest value (the first one on a tie)."""
    return max(range(len(values)), key=values.__getitem__)


def windows(moves: list[dict]) -> list[tuple[float, float]]:
    """Moves ({start, end}) merged into the stretches of time where something is moving."""
    out: list[list[float]] = []
    for m in sorted(moves, key=lambda m: m["start"]):
        if out and m["start"] <= out[-1][1]:
            out[-1][1] = max(out[-1][1], m["end"])
        else:
            out.append([m["start"], m["end"]])
    return [(a, b) for a, b in out]


def holds_between(wins: list[tuple[float, float]], min_s: float = HOLD_MIN_S) -> list[dict]:
    """The still stretches between moving windows that last at least `min_s`."""
    return [{"from": r(a1), "to": r(b0), "seconds": r(b0 - a1, 2)} for (_, a1), (b0, _) in zip(wins, wins[1:]) if b0 - a1 >= min_s]


def moving_runs(step_sizes: list[float], still: float) -> list[tuple[int, int]]:
    """(first, last) sample index of each run where the steps are bigger than `still`: step i goes from sample i to i + 1."""
    out: list[list[int]] = []
    for i, d in enumerate(step_sizes):
        if d <= still:
            continue
        if out and out[-1][1] == i:
            out[-1][1] = i + 1
        else:
            out.append([i, i + 1])
    return [(a, b) for a, b in out]


def jumps(step_sizes: list[float], floor: float, factor: float = JUMP_FACTOR) -> list[int]:
    """Steps (index i: from sample i to i + 1) bigger than `floor` and `factor` times bigger than both neighbours: a
    teleport or a one-frame snap, never a smooth fast move (whose neighbours are about as big)."""
    out = []
    for i, d in enumerate(step_sizes):
        around = [step_sizes[j] for j in (i - 1, i + 1) if 0 <= j < len(step_sizes)]
        if d > floor and around and all(d > factor * a for a in around):
            out.append(i)
    return out


def frame_spans(frames: list[int]) -> list[tuple[int, int]]:
    """Sorted frame numbers as runs of neighbours: [3, 4, 5, 9] -> [(3, 5), (9, 9)]."""
    out: list[list[int]] = []
    for f in sorted(frames):
        if out and f == out[-1][1] + 1:
            out[-1][1] = f
        else:
            out.append([f, f])
    return [(a, b) for a, b in out]
