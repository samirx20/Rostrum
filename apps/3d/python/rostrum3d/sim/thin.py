"""Thin a simulation's keys to the ones that matter (Turn into keys): a key the line between its neighbours already gives,
within a small tolerance, is dropped. A falling ball keeps a key at each bounce and a few along each arc; a copy at rest
keeps two. The kept keys replay every simulated frame within the tolerance (straight lines between frame keys can only
be off at a frame, so the frames bound the whole time).

    linear keys: Ramer-Douglas-Peucker on (frame, value), the error measured straight up (the value at that frame)
    held keys (Timing On 2s / 3s): a key holding the same value as the key before it is dropped
"""
from __future__ import annotations

POSITION_TOL = 0.001              # metres: 1 mm
TURN_TOL = 0.1                    # degrees
TOL = {"x": POSITION_TOL, "y": POSITION_TOL, "z": POSITION_TOL, "rx": TURN_TOL, "ry": TURN_TOL, "rz": TURN_TOL}


def kept(frames: list[int], values: list[float], tol: float, ease: str = "linear") -> list[int]:
    """The indices of `frames` / `values` to keep as keys (first and last always), ascending."""
    n = len(frames)
    if n <= 2:
        return list(range(n))
    if ease == "hold":
        out = [0]
        for i in range(1, n):
            if abs(values[i] - values[out[-1]]) > tol:
                out.append(i)
        return out if out[-1] == n - 1 else [*out, n - 1]
    keep, stack = {0, n - 1}, [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        fa, va, span = frames[a], values[a], frames[b] - frames[a]
        slope = (values[b] - va) / span
        worst, at = tol, -1
        for i in range(a + 1, b):
            err = abs(values[i] - (va + slope * (frames[i] - fa)))
            if err > worst:
                worst, at = err, i
        if at >= 0:
            keep.add(at)
            stack += [(a, at), (at, b)]
    return sorted(keep)


def thinned(frames: list[int], per: dict[str, list[float]], start: int, ease: str) -> dict[str, list[int]]:
    """{prop: the frames to key} for one body; `per[prop][f - start]` is its value at frame f."""
    return {p: [frames[i] for i in kept(frames, [vals[f - start] for f in frames], TOL[p], ease)]
            for p, vals in per.items()}
