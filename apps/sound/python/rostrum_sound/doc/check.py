"""The whole-document check, run after every call and every script merge: what single fields can't see."""
from __future__ import annotations

import re

from rostrum_core import RostrumError, did_you_mean
from rostrum_core.tree import walk

from .. import names
from . import effects as FX
from . import check_mix
from . import playing as PL
from . import times
from .registry import LISTS

TRACK_ID = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
LANE_RANGE = {"volume": (0, 4), "pan": (-1, 1), "level": (0, 4), "dynamics": (0, 2), "vibrato": (0, 1)}
NEEDS = {"notes": ("builtIn", "sfz", "model", "synth"), "hits": ("kit", "kitSfz"), "lines": ("voice",)}
STRING_POSITION = 0.03   # plucked strings are not plucked on the bridge itself (contract § 2a)


def _instrument(track) -> list[str]:
    out, kind, tid = [], track.get("instrument", "none"), track["id"]
    for key, ok in NEEDS.items():
        if track.get(key) and kind not in ok:
            out.append(f"track {tid} has {key} but its instrument is {kind!r} (needs {' or '.join(ok)})")
    if kind not in ("none", "voice") and not track.get(kind) and (track.get("notes") or track.get("hits")):
        out.append(f"track {tid}: instrument {kind} needs its {kind} file set before it can play its notes")
    drums = names.SYNTH_DRUMS if kind == "kit" else names.GM_DRUMS
    for h in track.get("hits", []) if kind in ("kit", "kitSfz") else []:
        d = h.get("drum")
        if isinstance(d, int) and kind == "kitSfz" and names.GM_KEYS[0] <= d <= names.GM_KEYS[1]:
            continue
        if d not in drums:
            out.append(f"{h['id']}: drum {d!r} is not on a {kind} kit (accepted: {', '.join(drums)})")
    return out + playing(track)


def _touch(who, holder, model) -> list[str]:
    out = []
    if model in names.BOWED:
        out += [f"{who}: {k} is not for {model} (a bowed voice)" for k in ("position", "hardness") if k in holder]
    if "damping" in holder and model not in names.PLUCKED:
        out.append(f"{who}: damping is for plucked strings only ({', '.join(names.PLUCKED)}), not {model}")
    if model in names.PLUCKED and holder.get("position", 1) < STRING_POSITION:
        out.append(f"{who}: position {holder['position']} is below {STRING_POSITION} for plucked strings")
    return out


def playing(track) -> list[str]:
    """Playing fields that only some instruments take (a note's field condition can't see its track)."""
    tid, model, kind = track["id"], track.get("model"), track.get("instrument", "none")
    arts = track.get("articulations") or {}
    out = _touch(f"track {tid}", track, model) if kind == "model" else []
    for n in track.get("notes", []):
        art, who = n.get("art"), n["id"]
        if art is not None and kind != "sfz":
            out.append(f"{who}: art {art!r} needs an sfz track with articulations (track {tid} is {kind})")
        elif art is not None and art not in arts:
            hint = did_you_mean(art, arts)
            out.append(f"{who}: art {art!r} is not one of track {tid}'s articulations "
                       f"(accepted: {', '.join(arts) or 'none set'})" + (f". {hint}" if hint else ""))
        touched = [k for k in PL.TOUCH_KEYS if k in n]
        if touched and kind != "model":
            verb = "applies" if len(touched) == 1 else "apply"
            out.append(f"{who}: {', '.join(touched)} only {verb} on a model track (track {tid} is {kind})")
        elif touched:
            out += _touch(who, n, model)
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
    out += check_mix.problems(data)
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
