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


STACKED = ("clip", "line")


def stack(blocks: list[dict]) -> None:
    """Clips and lines that overlap in time on one lane share it in rows (each its own `row` of
    `rows`, labels readable) instead of drawing over each other; `lanes` = the middle of its row, so a click picks
    the one under the pointer (block_at). Each overlapping group takes as few rows as it needs."""
    items = sorted((b for b in blocks if b["type"] in STACKED), key=lambda b: (b["t"], b["id"]))
    group, ends, group_end = [], [], -1.0
    for b in items + [None]:
        if b is None or b["t"] >= group_end - 1e-6:          # a new group: close the last one
            for g in group:
                g["rows"] = max(len(ends), 1)
                if g["rows"] > 1:
                    g["lanes"] = [(g["row"] + 0.5) / g["rows"]]
            if b is None:
                return
            group, ends = [], []
        row = next((i for i, e in enumerate(ends) if e <= b["t"] + 1e-6), None)
        if row is None:
            ends.append(b["t"] + b["dur"])
            row = len(ends) - 1
        else:
            ends[row] = b["t"] + b["dur"]
        b["row"] = row
        group.append(b)
        group_end = max(group_end, b["t"] + b["dur"])
