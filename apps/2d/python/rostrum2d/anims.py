"""A layer's animations, read from its keys (SPEC §9): the one source of truth for `anim.list` (agents) and the
timeline's stretches and lines (the screen). No data of its own: keys stay the document's data.

An **animation** is one setting's span from its first key to its last. X and Y of Position (W and H of Size, …) are one
setting: their keys make one animation. A **stretch** is the time between two neighbouring keys of one setting; its
ease is the ease of the keys it starts at (their ids are the stretch's `ids`: what `anim.ease` takes). **Lines**: the
animations of one layer that overlap in time go on separate lines, packed first-free; those that don't share line 0.
"""
from __future__ import annotations

from rostrum_core.keys import keys_of, key_value, marked, track_value

from . import fields as F

PAIRS = {"position": ("x", "y"), "size": ("w", "h"), "anchor": ("anchorX", "anchorY"), "stretch": ("scaleX", "scaleY"),
         "tilt": ("tiltX", "tiltY")}
LABELS = {"position": "Position", "size": "Size", "anchor": "Anchor", "stretch": "Stretch", "tilt": "Tilt"}
_OF = {p: s for s, ps in PAIRS.items() for p in ps}
# the plain word a person says for an animation (SPEC §9.3); any other setting goes by its own name
WORDS = {"position": "Move", "scale": "Scale", "stretch": "Scale", "rotation": "Turn", "opacity": "Fade", "size": "Size",
         "fill": "Colour", "color": "Colour", "d": "Shape", "blur": "Blur", "pathOffset": "Draw on", "rideAlong": "Follow"}
# the presets a person picks (SPEC §9.3) -> the key's `ease` in the document (rostrum_core.keys.easing)
PRESETS = {"linear": "linear", "smooth": "smooth", "in": "easeIn", "out": "easeOut", "spring": "spring",
           "bounce": "bounce", "hold": "hold"}
PRESET_LABELS = {"linear": "Linear", "smooth": "Smooth", "in": "In", "out": "Out", "spring": "Spring",
                 "bounce": "Bounce", "hold": "Hold"}
NAME_OF = {v: k for k, v in PRESETS.items()}


def setting_of(prop: str) -> str:
    return _OF.get(prop, prop)


def pack(spans: list[tuple[float, float]]) -> list[int]:
    """The line of each (start, end) span: first free line, in start order; spans that only touch don't overlap."""
    ends: list[float] = []                    # per line, where its last span ends
    lines = [0] * len(spans)
    for i in sorted(range(len(spans)), key=lambda i: (spans[i][0], spans[i][1])):
        a, b = spans[i]
        line = next((n for n, e in enumerate(ends) if a >= e - 1e-9), len(ends))
        if line == len(ends):
            ends.append(b)
        else:
            ends[line] = b
        lines[i] = line
    return lines


def _label(owner: dict, setting: str) -> str:
    if setting in LABELS:
        return LABELS[setting]
    p = F.param(owner["type"], setting)
    return p.label if p else setting


def animations(owner: dict, markers: dict | None = None, origin: float = 0.0) -> list[dict]:
    """[{setting, label, word, props, start, end, line, keys: [{id, t}], stretches: [...]}] of one layer (or effect,
    mask), in the owner's own seconds (keys on a shared marker placed through `markers`, `origin` as curve_of). A
    stretch: {ids (the keys it starts at), endIds, start, length, ease, preset, from: {prop: v}, to: {prop: v}}."""
    owner = {**owner, "keys": [dict(k) for k in owner.get("keys", [])]}
    if any(marked.marked(k) for k in owner["keys"]):
        marked.resolve(owner, markers, origin)
    by: dict[str, list[str]] = {}
    for k in owner["keys"]:
        by.setdefault(setting_of(k["prop"]), [])
        if k["prop"] not in by[setting_of(k["prop"])]:
            by[setting_of(k["prop"])].append(k["prop"])
    out = []
    for setting, props in by.items():
        props = [p for p in PAIRS.get(setting, (setting,)) if p in props]
        tracks = {p: sorted(keys_of(owner, p), key=lambda k: k["t"]) for p in props}
        times = sorted({round(k["t"], 6) for ks in tracks.values() for k in ks})
        if len(times) < 2:
            continue
        at = {t: [k for ks in tracks.values() for k in ks if abs(k["t"] - t) < 1e-6] for t in times}
        stretches = []
        for t0, t1 in zip(times, times[1:]):
            first = at[t0][0]
            ease = first.get("ease", "smooth")
            stretches.append({"ids": [k["id"] for k in at[t0]], "endIds": [k["id"] for k in at[t1]],
                              "start": t0, "length": round(t1 - t0, 6), "ease": ease, "preset": NAME_OF.get(ease, ""),
                              "from": {p: _value(tracks[p], t0) for p in props}, "to": {p: _value(tracks[p], t1) for p in props}})
        out.append({"setting": setting, "label": _label(owner, setting), "word": WORDS.get(setting, _label(owner, setting)),
                    "props": props, "start": times[0], "end": times[-1],
                    "keys": [{"id": k["id"], "t": t} for t in times for k in at[t]], "stretches": stretches})
    for a, line in zip(out, pack([(a["start"], a["end"]) for a in out])):
        a["line"] = line
    return out


def _value(keys: list[dict], t: float):
    """A prop's value at a stretch end: its own key there, else what its keys give then (X keyed, Y not)."""
    k = next((k for k in keys if abs(k["t"] - t) < 1e-6), None)
    if k is not None:
        return key_value(k)
    return track_value(keys, t) if keys and "v" in keys[0] else None
