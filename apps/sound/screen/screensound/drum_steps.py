"""The step tool on a drum grid (SPEC § 3.8): one stroke of the Draw tool along a drum row. No Qt.

A press on an empty step adds a hit; a press on a hit removes it; dragging on along the row does the same on every
grid step the pointer passes (a stroke that began on a hit erases). The steps are the window's grid cells
(`timing.lines_around`, so Grid ▾ and Snap decide them: the one snap). The calls are the document's own operations
(`hit.add`, `hit.remove`), previewed into ONE gesture, so a stroke is one undo step.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rostrum_sound.doc.select_time import start_of

from . import moves, timing

SAME = 0.010                  # seconds: a hit this close to a step is that step's (as hit.fill)
LEVELS = {0: None, 1: 1.0, 2: 0.5}      # modifier bits (Shift = 1, Alt = 2) -> accent (100 %), soft (50 %); else the default


@dataclass
class Stroke:
    drum: str
    erase: bool
    vel: float | None
    last: float                                   # the grid line the pointer was last on
    made: list = field(default_factory=list)      # the ids this stroke added (selected when it ends)
    done: set = field(default_factory=set)


def cell_of(t: float, root: dict, grid, px: float = 0.0) -> float:
    """The step under the pointer at `t`: the window's grid line at or before it (Snap off: exactly `t`)."""
    return timing.snap(t, root, False, grid, "cell", px)


def passed(root: dict, grid, last: float, now: float) -> list[float]:
    """The grid lines after `last` up to the one under `now`, in the order the pointer crossed them (either way)."""
    to = timing.lines_around(now, root, grid)[0]
    out, here, guard = [], timing.lines_around(last, root, grid), 0
    while guard < 512 and abs(here[0] - to) > 1e-6:
        guard += 1
        if to > here[0]:
            nxt = here[1]
        else:
            nxt = timing.lines_around(max(0.0, here[0] - 1e-4), root, grid)[0]
            if nxt >= here[0] - 1e-9:
                break
        out.append(nxt)
        here = timing.lines_around(nxt, root, grid)
    return out


def hits_in(doc, track: str, drum: str, a: float, b: float) -> list[str]:
    """The ids of `drum`'s hits that start from `a` up to `b` (seconds)."""
    root = doc.data
    return [h["id"] for h in doc.item(track).get("hits", []) if h["drum"] == drum and a - 1e-6 <= start_of(root, h) < b - 1e-6]


def calls_for(doc, track: str, stroke: Stroke, cells: list[float], grid, first_ids=()) -> list[dict]:
    """The calls for `cells` of a stroke: hits added on empty steps, or the step's hits removed (`first_ids`: the hit the
    press landed on, even when a humanised one sits off the line)."""
    root, out, gone = doc.data, [], set(first_ids)
    for c in cells:
        key = round(c, 4)
        if key in stroke.done:
            continue
        stroke.done.add(key)
        lo, hi = timing.lines_around(c, root, grid)
        if stroke.erase:
            gone.update(hits_in(doc, track, stroke.drum, lo, hi))
        elif not any(abs(start_of(root, h) - c) <= SAME for h in doc.item(track).get("hits", []) if h["drum"] == stroke.drum):
            call = moves.add_hit_call(doc, track, c, stroke.drum, free=True, grid=grid)
            if stroke.vel is not None:
                call["args"]["vel"] = stroke.vel
            out.append(call)
    if gone:
        out.append({"op": "hit.remove", "target": sorted(gone), "args": {}})
    return out


def fill_call(doc, track: str, drum: str, a: float, b: float, **amounts) -> dict:
    """`hit.fill` of `drum` from `a` to `b` seconds (written as beats, so a bar line is exact); `amounts`: every, offset,
    vel, accentEvery, accentVel (only the ones given)."""
    root = doc.data
    args = {"drum": drum, "from": {"beat": round(timing.beat(a, root), 6)}, "to": {"beat": round(timing.beat(b, root), 6)}}
    args.update({k: v for k, v in amounts.items() if v not in (None, "") and (v or k in ("offset", "vel"))})
    return {"op": "hit.fill", "target": [track], "args": args}
