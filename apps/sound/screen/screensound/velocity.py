"""The velocity strip's rules (no Qt; DESIGN.md §3.3d): a drag on a bar sets that note's velocity — every selected
note by the same proportion when the bar is one of them (Alt: all to the same value) — and a line drawn across
empty strip space gives every note under it (only the selected ones, if any are) the line's height. Each gesture
is `calls` of the existing `note.set` / `hit.set` (one value per note), so it is one undo step.
"""
from __future__ import annotations

LOWEST = 0.02                # a softest bar: still heard


def _vel(v: float) -> float:
    return round(min(1.0, max(LOWEST, v)), 3)


def grab(blocks: list[dict], ids, kind: str) -> list[dict]:
    """What each note / hit starts from: [{id, type, t, vel}] for the selected ones of `kind` (all of them when
    none is selected)."""
    mine = [b for b in blocks if b["type"] == kind]
    picked = [b for b in mine if b["id"] in ids]
    return [{"id": b["id"], "type": kind, "t": b["t"], "vel": float(b["vel"])} for b in (picked or mine)]


def _call(g: dict, v: float) -> dict:
    return {"op": f"{g['type']}.set", "target": [g["id"]], "args": {"vel": _vel(v)}}


def bar_calls(grabs: list[dict], primary: str, v: float, alt: bool = False) -> list[dict]:
    """The bar `primary` dragged to height `v`: the others follow by the same proportion (or, from a bar at about
    nothing, by the same amount); Alt sets them all to `v`."""
    start = next(g["vel"] for g in grabs if g["id"] == primary)
    out = []
    for g in grabs:
        if alt or g["id"] == primary:
            new = v
        elif start >= 0.05:
            new = g["vel"] * v / start
        else:
            new = g["vel"] + (v - start)
        out.append(_call(g, new))
    return out


def line_calls(grabs: list[dict], t0: float, v0: float, t1: float, v1: float) -> list[dict]:
    """A line from (t0, v0) to (t1, v1): each note whose start is on it takes the line's height there."""
    lo, hi = min(t0, t1), max(t0, t1)
    out = []
    for g in grabs:
        if lo - 1e-6 <= g["t"] <= hi + 1e-6:
            k = 0.0 if hi - lo < 1e-9 else (g["t"] - t0) / (t1 - t0)
            out.append(_call(g, v0 + (v1 - v0) * k))
    return out


def readout(picked: list[dict]) -> dict:
    """What the strip says of the selected notes / hits (`rollPicked`): how many of each kind, their lowest and highest
    velocity, and the earliest one's time (seconds) and velocity (the readout stands over it). A few numbers however
    many are selected: the strip once read every selected block, converted for each reader on every pick."""
    bs = [b for b in picked if b["type"] in ("note", "hit")]
    out = {"note": sum(1 for b in bs if b["type"] == "note"), "hit": sum(1 for b in bs if b["type"] == "hit")}
    if bs:
        first, vs = min(bs, key=lambda b: b["t"]), [b["vel"] for b in bs]
        out.update(lo=min(vs), hi=max(vs), t=first["t"], v=first["vel"])
    return out
