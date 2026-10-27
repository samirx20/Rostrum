"""The velocity strip's rules (no Qt; DESIGN.md §3.3d): a drag on a bar sets that note's velocity — every selected
note by the same proportion when the bar is one of them (Alt: all to the same value) — and a line drawn across
empty strip space gives every note under it (only the selected ones, if any are) the line's height. Each gesture
is `calls` of the existing `note.set` / `hit.set` (one value per note), so it is one undo step.
"""
from __future__ import annotations

LOWEST = 0.02                # a softest bar: still heard
STRIP_H, STRIP_MAX = 52, 240   # the strip's height (px): as it opens, and the most its top edge drags to


def strip_height(h: float) -> float:
    return float(round(min(STRIP_MAX, max(STRIP_H, float(h)))))


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


def line_calls(grabs: list[dict], t0: float, v0: float, t1: float, v1: float, reach: float = 0.0) -> list[dict]:
    """A line from (t0, v0) to (t1, v1): each note whose start is on it takes the line's height there. `reach`
    (seconds, a few screen px): a note that far past either end still counts, at that end's height (a line started
    a hair after the first note missed it: production round, hand #12)."""
    lo, hi = min(t0, t1), max(t0, t1)
    out = []
    for g in grabs:
        if lo - reach - 1e-6 <= g["t"] <= hi + reach + 1e-6:
            k = 0.0 if hi - lo < 1e-9 else min(1.0, max(0.0, (g["t"] - t0) / (t1 - t0)))
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


# ---- Ramp velocity… (note.ramp_velocity) ------------------------------------------------------------------------
def _ramp_notes(f) -> list[str]:
    return f.by_kind(("note",)).get("note", [])


def can_ramp(f) -> bool:
    """Notes selected that start at two or more times (a ramp across one chord means nothing)."""
    from rostrum_sound.doc.select_time import start_of
    ids = _ramp_notes(f)
    return len(ids) > 1 and f.once("ramp_times", lambda f: len({round(start_of(f.doc.data, f.doc.item(i)), 6)
                                                                for i in ids}) > 1)


def ramp_calls(f, a=None):
    a = a or {}
    return [{"op": "note.ramp_velocity", "target": _ramp_notes(f),
             "args": {k: a[k] for k in ("start", "end", "curve") if k in a}}]


def ramp_fit(f, a):
    """The popover starts from the selection's own ends: Start = the first note's velocity, End = the last one's."""
    from rostrum_sound.doc.select_time import start_of
    ns = sorted((f.doc.item(i) for i in _ramp_notes(f)), key=lambda n: start_of(f.doc.data, n))
    first, last = (float(ns[0].get("vel", 0.8)), float(ns[-1].get("vel", 0.8))) if ns else (0.5, 0.9)
    return {"start": {"default": round(first, 3), "fresh": True, "importance": "primary"},
            "end": {"default": round(last, 3), "fresh": True, "importance": "primary"},
            "curve": {"type": "choice", "options": [{"value": "linear", "label": "Straight"},
                                                    {"value": "ease", "label": "Ease in and out"}],
                      "importance": "secondary"}}
