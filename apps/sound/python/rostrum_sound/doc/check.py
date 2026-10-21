"""The whole-document check, run after every call and every script merge: what single fields can't see."""
from __future__ import annotations

import re

from rostrum_core import RostrumError
from rostrum_core.tree import walk

from .. import names
from . import effects as FX
from . import times
from .registry import LISTS

TRACK_ID = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
LANE_RANGE = {"volume": (0, 4), "pan": (-1, 1)}
NEEDS = {"notes": ("builtIn", "sfz"), "hits": ("kit", "kitSfz")}


def _instrument(track) -> list[str]:
    out, kind, tid = [], track.get("instrument", "none"), track["id"]
    for key, ok in NEEDS.items():
        if track.get(key) and kind not in ok:
            out.append(f"track {tid} has {key} but its instrument is {kind!r} (needs {' or '.join(ok)})")
    if kind in ("builtIn", "sfz", "kitSfz", "kit") and not track.get(kind):
        out.append(f"track {tid}: instrument {kind} needs its {kind} value set")
    drums = names.SYNTH_DRUMS if kind == "kit" else names.GM_DRUMS
    for h in track.get("hits", []) if kind in ("kit", "kitSfz") else []:
        d = h.get("drum")
        if isinstance(d, int) and kind == "kitSfz" and names.GM_KEYS[0] <= d <= names.GM_KEYS[1]:
            continue
        if d not in drums:
            out.append(f"{h['id']}: drum {d!r} is not on a {kind} kit (accepted: {', '.join(drums)})")
    return out


def _lane(item, root) -> list[str]:
    lo, hi = LANE_RANGE[item["lane"]]
    out, last = [], -1.0
    for t, v in item.get("points", []):
        try:
            s = times.seconds(t, root, item["id"])
        except RostrumError as e:
            return [f"{item['id']}: {e.subject} {e.problem}"]
        if s < last:
            out.append(f"{item['id']}: points are not in time order (at {t!r})")
        if not lo <= v <= hi:
            out.append(f"{item['id']}: {item['lane']} {v} is outside {lo} … {hi}")
        last = s
    return out


def _refs(value):
    """Every marker reference anywhere inside a value."""
    if isinstance(value, str) and times.marker_ref(value):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from _refs(v)


def check(data: dict) -> list[str]:
    out = []
    marks = [m.get("name") for m in data.get("markers", [])]
    out += [f"two markers are named {n!r}" for n in set(marks) if marks.count(n) > 1]
    for track in data.get("tracks", []):
        if not TRACK_ID.match(track["id"]):
            out.append(f"track id {track['id']!r} must be 1–64 letters, digits, _ . -")
        out += _instrument(track)
    for item in walk(data, LISTS):
        t = item.get("type")
        if t == "effect":
            out += FX.problems(item)
        elif t == "automation":
            out += _lane(item, data)
        for k, v in item.items():
            for ref in _refs(v):
                if times.marker_ref(ref) not in times.markers(data):
                    out.append(f"{item['id']}.{k}: no marker {times.marker_ref(ref)!r} for {ref!r}")
    return out
