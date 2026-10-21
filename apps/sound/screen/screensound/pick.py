"""What is under the pointer, from the data the screen draws (no Qt). The Timeline and the piano roll each take
clicks in one place and ask here, so a drag keeps working while the blocks it moves are redrawn.

`tol` is a few pixels, in seconds; `lane` / `row` say where in the row the pointer is.
"""
from __future__ import annotations


def _score(b, t, tol):
    """0 inside a block, the distance outside it (seconds), None when farther than tol."""
    end = b["t"] + max(b["dur"], tol)
    d = 0.0 if b["t"] - tol <= t <= end else min(abs(t - b["t"]), abs(t - end))
    return None if d > tol else d


def block_at(blocks: list[dict], t: float, lane: float, tol: float, lane_tol: float = 1.0) -> str:
    """In an arrangement row: the block at time t, nearest in lane (0 top .. 1 bottom; a block's `lanes`); "" when none."""
    best, key = "", None
    for b in blocks:
        s = _score(b, t, tol)
        if s is None:
            continue
        dl = min(abs(x - lane) for x in b.get("lanes", [lane]))
        if dl > lane_tol:
            continue
        k = (dl, s, -b["t"])
        if key is None or k < key:
            best, key = b["id"], k
    return best


def roll_at(roll: dict, t: float, row: float, tol: float) -> str:
    """In the piano roll: the note on key `row` (a MIDI number) or the hit on drum row `row` at time t, or a clip
    (any row); "" when none."""
    best, key = "", None
    for b in roll.get("blocks", []):
        if b["type"] == "note" and int(round(row)) not in b["keys"]:
            continue
        if b["type"] == "hit" and roll["drums"].index(b["drum"]) != int(round(row)):
            continue
        s = _score(b, t, tol)
        if s is not None and (key is None or (s, -b["t"]) < key):
            best, key = b["id"], (s, -b["t"])
    return best
