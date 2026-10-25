"""An item's animations, read from its keys (apps/2d SPEC §9): the one source of truth for `anim.list` (agents) and
the timeline's stretches and lines (the screen), in any app. No data of its own: keys stay the document's data.

An **animation** is one setting's span from its first key to its last. X and Y of Position (W and H of Size, …) are one
setting: their keys make one animation. A **stretch** is the time between two neighbouring keys of one setting; its
ease is the ease of the keys it starts at (their ids are the stretch's `ids`: what `anim.ease` takes). **Lines**: the
animations of one item that overlap in time go on separate lines, packed first-free; those that don't share line 0.
What an app calls its settings (which fields pair up, their labels and plain words) is its `Names`.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from . import marked
from .easing import label_of
from .evaluate import key_value, keys_of, track_value


@dataclass(frozen=True)
class Names:
    """What an app calls its settings: `pairs` ({"position": ("x", "y")}: fields keyed together make one setting),
    `labels` ({"position": "Position"}), `words` (the plain word a person says for an animation: {"position": "Move"}),
    `label` (owner, setting) -> a label for any other setting, or None (the setting's own name is used)."""
    pairs: dict = field(default_factory=dict)
    labels: dict = field(default_factory=dict)
    words: dict = field(default_factory=dict)
    label: Callable[[dict, str], str | None] = lambda owner, setting: None

    def setting_of(self, prop: str) -> str:
        return next((s for s, ps in self.pairs.items() if prop in ps), prop)

    def label_of(self, owner: dict, setting: str) -> str:
        return self.labels.get(setting) or self.label(owner, setting) or setting


PLAIN = Names()      # every field its own setting, named by itself


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


def animations(owner: dict, names: Names = PLAIN, markers: dict | None = None, origin: float = 0.0) -> list[dict]:
    """[{setting, label, word, props, start, end, line, keys: [{id, t}], stretches: [...]}] of one item (a layer, an
    effect, a mask, a 3D object), settings named by the app's `names`, in the owner's own seconds (keys on a shared marker placed through `markers`, `origin` as curve_of). A
    stretch: {ids (the keys it starts at), endIds, start, length, ease (its id in EASE_LIST), easeLabel, from: {prop: v}, to: {prop: v}}."""
    owner = {**owner, "keys": [dict(k) for k in owner.get("keys", [])]}
    if any(marked.marked(k) for k in owner["keys"]):
        marked.resolve(owner, markers, origin)
    by: dict[str, list[str]] = {}
    for k in owner["keys"]:
        props = by.setdefault(names.setting_of(k["prop"]), [])
        if k["prop"] not in props:
            props.append(k["prop"])
    out = []
    for setting, props in by.items():
        props = [p for p in names.pairs.get(setting, (setting,)) if p in props]
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
                              "start": t0, "length": round(t1 - t0, 6), "ease": ease, "easeLabel": label_of(ease),
                              "from": {p: _value(tracks[p], t0) for p in props}, "to": {p: _value(tracks[p], t1) for p in props}})
        label = names.label_of(owner, setting)
        out.append({"setting": setting, "label": label, "word": names.words.get(setting, label),
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
