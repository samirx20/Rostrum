"""Item handles (no Qt; apps/sound/DESIGN.md §3.0 "Dragging items and their handles", §3.9): on a clip the left /
right edge trims, the top corners set the fades, the bottom-right corner stretches, the level line sets its volume;
on a note (the Editor) the right end sets its length. `at` says which handle is under the pointer; `calls` turns a
drag into one `clip.set_one` / `note.set` per selected item (every one gets the same change), and `label` names the
step ("Trim clip", "Fade in 0.40 s").
"""
from __future__ import annotations

import math

from rostrum_sound.doc import select_time as ST
from rostrum_sound.doc.shift import write_like

from . import timing

CORNER = 0.3                 # the top / bottom part of a clip's height that is a corner handle
LEVEL_NEAR = 0.12            # how near (in clip heights) the pointer must be to the level line
MIN_S = 0.02                 # the shortest a trimmed clip or a note can get (seconds)
DB_PER_HEIGHT = 24           # the level line: a whole clip height of drag = 24 dB
NAMES = {"start": "Trim clip", "end": "Trim clip", "stretch": "Stretch clip", "fadeIn": "Fade in",
         "fadeOut": "Fade out", "level": "Clip level", "length": "Note length"}


def level_y(volume: float) -> float:
    """Where a clip's level line is drawn, 0 top .. 1 bottom (1 = as recorded sits a third from the top)."""
    db = 20 * math.log10(max(volume, 1e-4))
    return min(1.0, max(0.0, 1 / 3 - db / DB_PER_HEIGHT))


def at(block: dict, t: float, y: float, tol: float) -> str:
    """The handle of a clip block under the pointer (time t, height y 0..1 in the clip), "" for its body."""
    s, e = block["t"], block["t"] + block["dur"]
    if not s - tol <= t <= e + tol:
        return ""
    if y < CORNER and abs(t - (s + block.get("fadeIn", 0))) <= tol:
        return "fadeIn"
    if y < CORNER and abs(t - (e - block.get("fadeOut", 0))) <= tol:
        return "fadeOut"
    if y > 1 - CORNER and abs(t - e) <= tol:
        return "stretch"
    if abs(t - s) <= tol:
        return "start"
    if abs(t - e) <= tol:
        return "end"
    if abs(y - level_y(block.get("volume", 1))) <= LEVEL_NEAR:
        return "level"
    return ""


def grab(doc, ids, handle) -> list[dict]:
    """What each selected item starts from (only the kind the handle belongs to)."""
    root, kind = doc.data, "note" if handle == "length" else "clip"
    out = []
    for i in ids:
        it = doc.item(i)
        if it["type"] != kind:
            continue
        s = ST.start_of(root, it)
        g = {"id": i, "it": it, "s": s, "dur": ST.end_of(root, it) - s}
        if kind == "clip":
            g.update(src=ST.source_length(it, root), sp=ST.speed(it), file=ST.file_seconds(it))
        out.append(g)
    return out


def calls(doc, grabs, handle, dt, dy, free) -> list[dict]:
    root, out = doc.data, []
    for g in grabs:
        it, s, dur = g["it"], g["s"], g["dur"]
        if handle == "length":
            end = s + max(MIN_S, dur + dt) if free else max(s + MIN_S, timing.snap(s + dur + dt, root, False))
            args = {"dur": timing.write_length(it["dur"], end - s, root, s)}
            out.append({"op": "note.set", "target": [g["id"]], "args": args})
            continue
        sp, inn = g["sp"], float(it.get("in", 0))
        if handle == "start":
            to = s + dt if free else timing.snap(s + dt, root, False)
            d = min(max(to - s, -inn / sp), dur - MIN_S)
            args = {"at": write_like(it["at"], s + d, root), "in": round(inn + d * sp, 4),
                    "length": ST.length_like(it.get("length"), g["src"] - d * sp, root, s + d, it)}
        elif handle == "end":
            to = s + dur + dt if free else timing.snap(s + dur + dt, root, False)
            src = min(max(MIN_S, to - s) * sp, g["file"] - inn)
            args = {"length": ST.length_like(it.get("length"), src, root, s, it)}
        elif handle in ("fadeIn", "fadeOut"):
            old = float(it.get(handle, 0))
            args = {handle: round(min(max(0.0, old + (dt if handle == "fadeIn" else -dt)), dur), 3)}
        elif handle == "level":
            v = float(it.get("volume", 1)) * 10 ** (-dy * DB_PER_HEIGHT / 20)
            args = {"volume": round(min(max(v, 0.0), 4.0), 4)}
        else:                                                  # stretch: the clip lasts longer, the file plays slower
            k = max(MIN_S, dur + dt) / max(dur, MIN_S)
            args = {"stretch": round(min(max(float(it.get("stretch", 1)) * k, 0.25), 4.0), 4)}
        out.append({"op": "clip.set_one", "target": [g["id"]], "args": args})
    return out


def label(doc, grabs, handle) -> str:
    """The step's name, from the first item as it is now ("Fade in 0.40 s", "Clip level -3.0 dB")."""
    words, n = NAMES[handle], len(grabs)
    more = f" ({n} {'notes' if handle == 'length' else 'clips'})" if n > 1 else ""
    if not grabs or not doc.has(grabs[0]["id"]):
        return words + more
    it = doc.item(grabs[0]["id"])
    if handle in ("fadeIn", "fadeOut"):
        return f"{words} {float(it.get(handle, 0)):.2f} s{more}"
    if handle == "level":
        return f"{words} {20 * math.log10(max(float(it.get('volume', 1)), 1e-4)):+.1f} dB{more}"
    return words + more
