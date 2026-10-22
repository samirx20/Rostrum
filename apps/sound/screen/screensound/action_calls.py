"""The operation calls behind the selection's actions (actions.py), as plain functions of `Facts` (what is selected,
the playhead, the time range). No Qt. Each returns the calls one action applies as one change; an operation's own
checks decide whether it can run (`tries`: a dry run, so Join and Crossfade are listed only when they would work).
"""
from __future__ import annotations

import math

from rostrum_core import RostrumError, run
from rostrum_sound.doc import select_time as ST

TIMED = ("note", "hit", "clip")                       # what has `<kind>.duplicate` / `.move`
REMOVABLE = ("note", "hit", "clip", "line", "track", "marker", "section")


class Facts:
    """What the selection is: ids in pick order, their items and kinds, their tracks, the playhead, the range."""

    def __init__(self, doc, ids, playhead=0.0, rng=None, clipboard=False, track=""):
        self.doc, self.ids, self.count = doc, list(ids), len(ids)
        self.items = [doc.item(i) for i in self.ids]
        self.kinds = {it["type"] for it in self.items}
        self.one = next(iter(self.kinds)) if len(self.kinds) == 1 else ""
        self.parents = {doc.parent_of(i)[0] for i in self.ids if self.one != "track"}
        self.playhead, self.range, self.clipboard, self.track = playhead, rng, clipboard, track

    def by_kind(self, kinds=TIMED):
        out: dict[str, list[str]] = {}
        for it in self.items:
            if it["type"] in kinds:
                out.setdefault(it["type"], []).append(it["id"])
        return out


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
    has no length, and the groove stays on the beat)."""
    root = f.doc.data
    items = [it for it in f.items if it["type"] in TIMED]
    start = min(ST.start_of(root, i) for i in items)
    end = max(ST.end_of(root, i) for i in items)
    if f.kinds <= {"note", "hit"}:
        beat = max(ST.delta(root, start, {"beats": 1}), 1e-6)
        return {"beats": max(1, math.ceil((end - start) / beat - 1e-6))}
    return round(max(end - start, 0.01), 4)


def can_move(f, step) -> bool:
    """A track can go up (-1) / down (1): some selected track has an unselected one on that side."""
    order = [t["id"] for t in f.doc.data.get("tracks", [])]
    picked = set(f.ids)
    return any(0 <= order.index(i) + step < len(order) and order[order.index(i) + step] not in picked for i in f.ids)


def range_clips(f) -> list[str]:
    """The clips a Delete on the time range cuts: the selected clips, or (nothing selected) those on the Editor's
    track; only those the range reaches into."""
    root, (a, b) = f.doc.data, f.range
    if f.count:
        clips = f.items if f.one == "clip" else []
    else:
        clips = f.doc.item(f.track).get("clips", []) if f.track and f.doc.has(f.track) else []
    return [c["id"] for c in clips if ST.start_of(root, c) < b - 1e-6 and ST.end_of(root, c) > a + 1e-6]


def cut_range(f):
    ids = range_clips(f)
    if not ids or len({f.doc.parent_of(i)[0] for i in ids}) != 1:
        return []
    return [call("clip.cut_range", ids, at=round(f.range[0], 4), end=round(f.range[1], 4))]


def duplicate(f):
    if f.one == "track":
        return [call("track.duplicate", f.ids)]
    by = span_by(f)
    return [call(f"{k}.duplicate", ids, by=by) for k, ids in f.by_kind().items()]


def delete(f):
    return [call(f"{k}.remove", ids) for k, ids in f.by_kind(REMOVABLE).items()]


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


def range_duplicate(f):
    by = round(f.range[1] - f.range[0], 4)
    held = Facts(f.doc, inside(f)).by_kind()
    return [call(f"{k}.duplicate", ids, by=by) for k, ids in held.items()]


def section(f):
    have = {s.get("name") for s in f.doc.data.get("sections", [])}
    n = len(have) + 1
    while f"Section {n}" in have:
        n += 1
    return [{"op": "section.add", "args": {"name": f"Section {n}", "at": round(f.range[0], 4), "end": round(f.range[1], 4)}}]
