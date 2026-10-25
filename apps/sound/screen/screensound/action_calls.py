"""The operation calls behind the selection's actions (actions.py), as plain functions of `Facts` (what is selected,
the playhead, the time range). No Qt. Each returns the calls one action applies as one change; an operation's own
checks decide whether it can run (`tries`: a dry run, so Join and Crossfade are listed only when they would work).
"""
from __future__ import annotations

import math

from rostrum_core import RostrumError, run
from rostrum_sound.doc import meter
from rostrum_sound.doc import select_time as ST

from . import song_edit
from .facts import TIMED, Facts  # noqa: F401  (Facts is read here by every action file: C.Facts)
from .moves import remove_calls

REMOVABLE = ("note", "hit", "clip", "line", "track", "marker", "section")


def call(op, target, /, **args):
    return {"op": op, "target": list(target), "args": args}


def tries(f, calls) -> bool:
    """The operation's own checks decide (one source of truth): a dry run that refuses = the action is absent."""
    try:
        run.plan(f.doc.kind, f.doc.data, calls)
        return True
    except RostrumError:
        return False


def clips_one_track(f):
    return f.one == "clip" and f.count >= 2 and len(f.parents) == 1


def span_by(f):
    """How far a copy sits after the original: the selection's span; notes and hits round up to whole beats (a hit
    has no length, and the groove stays on the beat). Kept for the same song and selection (every item's start and
    end in seconds: ~15 ms a time for 3,000 notes, and the action list asks on every change)."""
    return f.once("span", _span)


def _span(f):
    root = f.doc.data
    items = [it for it in f.items if it["type"] in TIMED]
    start = min(ST.start_of(root, i) for i in items)
    end = max(ST.end_of(root, i) for i in items)
    if f.kinds <= {"note", "hit"}:
        beat = max(ST.delta(root, start, {"beats": 1}), 1e-6)
        return {"beats": max(1, math.ceil((end - start) / beat - 1e-6))}
    return round(max(end - start, 0.01), 4)


def nudge(f, beats) -> list[dict]:
    """← →: the selection's notes, hits and clips move as one block by `beats`. A step that would put the earliest
    before the song's start moves the block to the start (the spacing kept); already there: [] (the key refuses)."""
    by = f.by_kind()
    if beats < 0 and by:
        root = f.doc.data
        first = ST.tempo.beat_at(root, min(ST.start_of(root, f.doc.item(i)) for ids in by.values() for i in ids))
        if first < 1e-6:
            return []
        beats = max(beats, -first)
    return [call(f"{k}.move", ids, by={"beats": beats}) for k, ids in by.items()]


def can_move(f, step) -> bool:
    """A track can go up (-1) / down (1): some selected track has an unselected one on that side."""
    order = [t["id"] for t in f.doc.data.get("tracks", [])]
    picked = set(f.ids)
    return any(0 <= order.index(i) + step < len(order) and order[order.index(i) + step] not in picked for i in f.ids)


def range_clips(f) -> list[str]:
    """The clips a Delete on the time range cuts: the selected clips (unless the range was drawn after them), the
    clips of the selected tracks, else those on the Editor's track; only those the range reaches into."""
    root, (a, b) = f.doc.data, f.range
    if f.one == "clip" and not f.on_range:
        clips = f.items
    elif f.one == "track":
        clips = [c for t in f.items for c in t.get("clips", [])]
    else:
        clips = f.doc.item(f.track).get("clips", []) if f.track and f.doc.has(f.track) else []
    return [c["id"] for c in clips if ST.start_of(root, c) < b - 1e-6 and ST.end_of(root, c) > a + 1e-6]


def cut_range(f):
    ids = range_clips(f)
    if not ids or len({f.doc.parent_of(i)[0] for i in ids}) != 1:
        return []
    return [call("clip.cut_range", ids, at=round(f.range[0], 4), end=round(f.range[1], 4))]


def group_buses(f) -> list[str]:
    """The groups a selection means: the selected buses, or the one bus every selected track plays into."""
    if f.one == "bus":
        return f.ids
    out = {it.get("output") for it in f.items} if f.one == "track" else set()
    return [b] if len(out) == 1 and (b := out.pop()) in {x["id"] for x in f.doc.data.get("buses", [])} else []


def is_whole_group(f) -> bool:
    """The selected tracks are exactly one group's tracks: grouping them again means nothing (Ungroup is the action)."""
    buses = group_buses(f) if f.one == "track" else []
    return bool(buses) and set(f.ids) == {t["id"] for t in f.doc.data.get("tracks", []) if t.get("output") == buses[0]}


def delete_time(f):
    return [call("range.remove", [], at=round(f.range[0], 4), end=round(f.range[1], 4))]


def insert_time(f):
    return [call("range.insert", [], at=round(f.range[0], 4), length=round(f.range[1] - f.range[0], 4))]


def duplicate(f, **repeat):
    """Ctrl+D (one copy); `repeat`: Repeat…'s `times` or `until` (amount_actions.py)."""
    if f.one == "track":
        return [call("track.duplicate", f.ids)]
    by = span_by(f)
    return [call(f"{k}.duplicate", ids, by=by, **repeat) for k, ids in f.by_kind().items()]


def delete(f):
    return [c for k, ids in f.by_kind(REMOVABLE).items() for c in remove_calls(f.doc, k, ids)]


def toggle_all(field):
    def calls(f):
        on = not all(it.get(field) for it in f.items)
        return [call("track.set", f.ids, **{field: on})]
    return calls


def flip(field, on_word, off_word):
    return lambda f: off_word if all(it.get(field) for it in f.items) else on_word


def layer_name(f):
    have = {c.get("group") for t in f.doc.data.get("tracks", []) for c in t.get("clips", [])}
    n = 1
    while f"Layer {n}" in have:
        n += 1
    return f"Layer {n}"


def inside(f):
    """The ids of notes, hits and clips that start inside the range (any track)."""
    t0, t1 = f.range
    root = f.doc.data
    return [it["id"] for t in root.get("tracks", []) for k in ("notes", "hits", "clips") for it in t.get(k, [])
            if t0 - 1e-6 <= ST.start_of(root, it) < t1 - 1e-6]


def range_duplicate(f, **repeat):
    """Ctrl+D on a time range: everything inside, copied by the range's length (one change); `repeat`: Repeat…'s
    `times` or `until`, the same `by` for every kind so the copies stay together."""
    by = round(f.range[1] - f.range[0], 4)
    return [call(f"{k}.duplicate", ids, by=by, **repeat) for k, ids in Facts(f.doc, inside(f)).by_kind(TIMED).items()]


def section(f):
    """The time range as a section, named like "+ Section" names one (its next role: intro, verse …)."""
    name = song_edit.section_name({s.get("name") for s in f.doc.data.get("sections", [])})
    return [{"op": "section.add", "args": {"name": name, "at": round(f.range[0], 4), "end": round(f.range[1], 4)}}]


def bar_near(f) -> int:
    """The bar nearest the selected marker at today's tempo (the popover's starting number)."""
    root = f.doc.data
    t = ST.start_of(root, f.items[0])
    return max(2, round(meter.bar_at(root, ST.tempo.beat_at(root, t))) + 1)


def fit_bar(f, bar=None):
    name = f.items[0].get("name") or f.ids[0]
    return [{"op": "tempo.fit_bar", "args": {"marker": name, "bar": int(bar if bar is not None else bar_near(f))}}]
