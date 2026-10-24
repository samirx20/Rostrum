"""The whole-document check, run after every call and every script merge: what single fields can't see."""
from __future__ import annotations

import re

from rostrum_core import RostrumError, did_you_mean
from rostrum_core.tree import walk

from .. import names
from . import effects as FX
from . import check_mix
from . import lanes as LN
from . import playing as PL
from . import meter, sections
from . import markers, times
from .registry import LISTS

TRACK_ID = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
NEEDS = {"notes": ("builtIn", "sfz", "model", "synth", "plugin"), "hits": ("kit", "kitSfz", "plugin"), "lines": ("voice",)}
STRING_POSITION = 0.03   # plucked strings are not plucked on the bridge itself (contract § 2a)


def _instrument(track) -> list[str]:
    out, kind, tid = [], track.get("instrument", "none"), track["id"]
    for key, ok in NEEDS.items():
        if track.get(key) and kind not in ok:
            out.append(f"track {tid} has {key} but its instrument is {kind!r} (needs {' or '.join(ok)})")
    if kind not in ("none", "voice") and not track.get(kind) and (track.get("notes") or track.get("hits")):
        out.append(f"track {tid}: instrument {kind} needs its {kind} file set before it can play its notes")
    drums = names.SYNTH_DRUMS if kind == "kit" else names.GM_DRUMS
    unknown: dict = {}      # one message per unknown drum name, not one per hit
    for h in track.get("hits", []) if kind in ("kit", "kitSfz") else []:
        d = h.get("drum")
        if isinstance(d, int) and kind == "kitSfz" and names.GM_KEYS[0] <= d <= names.GM_KEYS[1]:
            continue
        if d not in drums:
            unknown.setdefault(d, []).append(h["id"])
    for d, ids in unknown.items():
        more = f" and {len(ids) - 1} more hit(s)" if len(ids) > 1 else ""
        near = names.KIT_NEAREST[kind].get(names.drum_key(d)) if isinstance(d, str) else None
        write = f': write "{near}" (the nearest drum this kit has)' if near else ""
        out.append(f"{ids[0]}{more}: drum {d!r} is not on track {tid}'s {'synth' if kind == 'kit' else 'SFZ'} kit{write} (accepted: {', '.join(drums)})")
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
    """Points in time order and inside the lane's range: an automation child, or an effect's envelope settings."""
    if item["type"] == "automation":
        owner = item["id"].split(".auto_")[0]
        of = f'track {owner}' if any(t["id"] == owner for t in root.get("tracks", [])) else owner
        return _points(item["id"], item["lane"], item.get("points", []), LN.MIX_RANGE[item["lane"]], root,
                       f'the {names.LANE_WORDS.get(item["lane"], item["lane"])} lane of {of}')
    return [p for lane in LN.offered(item) for p in        # (an effect's ranges: FX.problems)
            _points(item["id"], lane, LN.points(item, lane), None, root)]


def _points(who, lane, pts, rng, root, words=None) -> list[str]:
    out, last = [], -1.0
    for t, v in pts:
        try:
            s = times.seconds(t, root, who)
        except RostrumError as e:
            return [f"{who}: {e.subject} {e.problem}"]
        if s < last:
            out.append(f"{who}: {lane} points are not in time order (at {t!r})")
        if rng and not rng[0] <= v <= rng[1]:
            out.append(f"{words}: {v} is outside {rng[0]} … {rng[1]}" if words else f"{who}: {lane} {v} is outside {rng[0]} … {rng[1]}")
        last = s
    return out


def _refs(value):
    """Every marker reference anywhere inside a value."""
    if isinstance(value, str) and markers.ref(value):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from _refs(v)


_SEEN = {"markers": [], "marks": None}   # the markers the last check saw (their items, so `is` compares them)


def _ref_holders(data: dict, items, marks: list):
    """The items whose marker references need checking: only the changed ones while the markers are the very same
    items as the last check saw and no tempo changed (a version shares unchanged items: rostrum_core edits.fork), else every item."""
    own = data.get("markers", [])
    same = (items is not None and not any(i.get("type") in ("doc", "tempo", "meter") for i in items) and marks == _SEEN["marks"] and len(own) == len(_SEEN["markers"])
            and all(a is b for a, b in zip(own, _SEEN["markers"])))
    _SEEN.update(markers=list(own), marks=marks)
    return items if same else walk(data, LISTS)


def check(data: dict, items=None) -> list[str]:
    """`items`: the items a call changed (None: everything, as on open). Track and song rules are always checked
    whole; marker references only in the changed items unless a marker changed."""
    out = []
    try:
        marks = [markers.key(n) for n, _ in markers.items(data)]
    except RostrumError as e:                           # a local marker named like a project one
        return [str(e)]
    out += [f"two markers are named {n!r}" for n in set(marks) if marks.count(n) > 1]
    out += check_mix.problems(data)
    out += sections.problems(data)
    for m in () if items is None else (i for i in items if i.get("type") == "meter" and "at" in i):
        out += [p] if (p := meter.off_bar(data, m)) else []         # an old song still opens; a new change is on a bar
    for track in data.get("tracks", []):
        if not TRACK_ID.match(track["id"]):
            out.append(f"track id {track['id']!r} must be 1–64 letters, digits, _ . -")
        out += _instrument(track)
    for item in _ref_holders(data, items, marks):
        t = item.get("type")
        if t == "effect":
            out += FX.problems(item) + _lane(item, data)
        elif t == "automation":
            out += _lane(item, data)
        for k, v in item.items():
            for ref in () if k == "colour" else _refs(v):         # a colour ("#4aa3ff") is not a marker
                if markers.key(markers.ref(ref)) not in marks:
                    out.append(f"{item['id']}.{k}: no marker {markers.ref(ref)!r} for {ref!r}")
    return out
