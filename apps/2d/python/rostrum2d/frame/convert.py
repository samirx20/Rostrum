"""An older file's cameras turned into its scenes' frames (apps/2d/FRAME.md › Older files; format 2 → 3, run on open
by migrations.py before the document is checked). Data only, on the opened copy:

1. No camera: the frame at home, still. The engine writes nothing for it: the export is byte for byte what it was.
2. One camera showing for the whole scene: its fields, keys, expressions and ride move to the frame (home at the
   output centre, where the old maths had it): the pictures are the same at every moment.
3. Several cameras, one that doesn't show all the time, or cameras timed on shared markers: the frame's track is
   built shot by shot (`shots.py`), each shot's keys and its cut still on its marker (so moving the marker moves the
   cut, as it moved the camera).

Expressions that read an old camera's field read the frame's instead."""
from __future__ import annotations

import re

from rostrum_core.keys import marked
from rostrum_core.keys.ops import key_id
from rostrum_core.marker_times import lookup, times
from rostrum_core.tree import walk

from .. import fields as F, retime
from . import TYPE, make, shots

MOVED = {p.name for p in F.FIELDS[TYPE]} - {"homeX", "homeY", "locked"}


def _whole(cam: dict, comp: dict) -> bool:
    dur = comp.get("duration", F.defaults("comp")["duration"])
    return (not retime._any_timed(cam) and cam.get("start", 0.0) <= 0
            and cam.get("end", retime.END_OF_COMP) >= dur)


def _move(cam: dict, frame: dict):
    """Case 2: the one camera's settings, keys and expressions become the frame's (ids follow the frame's)."""
    frame.update({k: v for k, v in cam.items() if k in MOVED})
    frame["keys"] = [{**k, "id": key_id(frame["id"], k["prop"], k["t"])} for k in cam.get("keys", []) if k.get("prop") in MOVED]
    frame["exprs"] = [{**e, "id": f'{frame["id"]}.{e["prop"]}.expr'} for e in cam.get("exprs", []) if e.get("prop") in MOVED]


def _refs(data: dict, lists: dict, old: set[str], new: str):
    """Expressions naming an old camera (`cam.x`, `ref("cam.x")`) name the frame."""
    if not old:
        return
    pattern = re.compile(r'(?<![\w.])(' + "|".join(map(re.escape, sorted(old, key=len, reverse=True))) + r')(?=\.)')
    for item in walk(data, lists):
        if item.get("type") == "expr" and isinstance(item.get("source"), str):
            item["source"] = pattern.sub(new, item["source"])


def _placed(comp: dict, cams: list[dict], markers: dict, notes: list) -> list[dict]:
    """The cameras with every time in scene seconds (retime.py), on copies; a marker the project doesn't have (or no
    project) reads as 0 s, said in the label, so the file still opens. (The frame has no `start`, so retime leaves
    the old field alone: it is shifted here.)"""
    fps = comp.get("fps", F.defaults("comp")["fps"])
    names = {n for c in cams for n in (c.get("marker"), c.get("endMarker"), *marked.names(c)) if n}
    if any(lookup(markers, n) is None for n in names):
        notes.append("cameras timed on markers the project doesn't have were read as if those markers were at 0 s")
        markers = {**{n: 0.0 for n in names}, **markers}
    out = retime.timed({"layers": cams}, markers, fps)["layers"]
    for old, new in zip(cams, out):
        new["start"] = old.get("start", 0.0) + (lookup(markers, old["marker"]) if old.get("marker") else 0.0)
    return out


def convert(data: dict, lists: dict, folder=None):
    markers = times(folder)
    taken = {i["id"] for i in walk(data, lists) if i.get("type") != TYPE}
    notes, moved = [], 0
    for comp in data.get("comps", []):
        cams = [l for l in comp.get("layers", []) if l.get("type") == TYPE]
        comp["layers"] = [l for l in comp.get("layers", []) if l.get("type") != TYPE]
        frame = make.new(comp, taken)
        taken.add(frame["id"])
        if len(cams) == 1 and _whole(cams[0], comp):
            _move(cams[0], frame)
        elif cams:
            notes += shots.track(comp, _placed(comp, cams, markers, notes), frame, markers)
        moved += len(cams)
        _refs(data, lists, {c["id"] for c in cams}, frame["id"])
        comp["layers"].insert(0, frame)
    if not moved:
        return data, "Each scene has its frame (the box that is exported), at home"
    return data, "This piece's camera is now its frame" + (f" ({'; '.join(notes)})" if notes else "")
