"""Layers timed from a shared marker: the one place a layer's own times become composition times.

A layer whose `marker` names a shared marker ("logo lands") counts its times from that marker: its `start`, `end`,
keys, and those of everything inside it (effects, masks, child layers, a rig's bones, a drawing's frames). Move the
marker in any app and the whole layer moves with it (AGENTS.md rule 8: cross-app timing by named markers, never
copied numbers). A layer inside a timed group with a `marker` of its own counts from its own marker. `endMarker` ends a layer on
another marker ("the phone shot ends on reveal"); `start` may be below 0 (a lead-in before its marker).

A key may be timed on a marker of its own (`"t": "#drop+0.2"`, rostrum_core.keys.marked): it lands at that moment
of the project, whatever its layer counts from, before the layer's start too (a pre-roll); `offset_of` says where
an item's own time 0 sits, and `placed` gives the composition as written with those keys in their owner's seconds
(the timeline and curve editor read that).

`timed(comp, markers, fps)` returns the composition with every time in composition seconds (a copy, only when some
layer is timed); the scene description and the motion facts read that, so preview, export and the look tools agree.
The document keeps the times as written (from the marker). A marker that isn't in the project fails loudly.
"""
from __future__ import annotations

import copy

from rostrum_core.errors import RostrumError, codes
from rostrum_core.keys import marked
from rostrum_core.marker_times import lookup

from . import fields as F

FIELD, END = "marker", "endMarker"
CHILDREN = ("effects", "masks", "layers", "bones", "iks", "binds")
END_OF_COMP = 36000.0               # `end`'s "End of comp" word (fields.py): stays the end of the comp


def _any_timed(node: dict) -> bool:
    return (bool(node.get(FIELD) or node.get(END)) or any(marked.marked(k) for k in node.get("keys", []))
            or any(_any_timed(c) for key in CHILDREN for c in node.get(key, [])))


def _at(item: dict, field: str, markers: dict | None) -> float:
    name = item[field]
    at = lookup(markers or {}, name)            # names match as keys' markers do: case and spaces ignored
    if at is None:
        raise RostrumError(codes.NOT_FOUND, f'{item["id"]}.{field}', f'marker "{name}"', "is not in the project",
                           hint=f'Markers: {", ".join(sorted(markers or {})) or "none"}. Add it (edit_markers) or clear the field.')
    return float(at)


def _offset(item: dict, inherited: float, markers: dict | None) -> float:
    return _at(item, FIELD, markers) if item.get(FIELD) else inherited


def _shift(item: dict, off: float, fps: float, markers: dict | None) -> None:
    for key in CHILDREN:
        for child in item.get(key, []):
            _shift(child, _offset(child, off, markers), fps, markers)
    if item.get(END):                  # ends on a marker: that moment, whatever the layer counts from
        item["end"] = _at(item, END, markers) - off
    for k in item.get("keys", []):     # a key on a marker: that moment; the others count from the layer's
        k["t"] = k["t"] + off if not marked.marked(k) else k["t"]
    marked.resolve(item, markers)
    if not off:
        return
    if F.param(item["type"], "start") is not None:     # layers (effects, masks and bones have no start)
        item["start"] = item.get("start", 0.0) + off
    if item.get("end", END_OF_COMP) < END_OF_COMP:
        item["end"] = item["end"] + off
    for f in item.get("frames", []):  # a drawing's frames are composition frame numbers
        f["at"] = f["at"] + round(off * fps)


def timed(comp: dict, markers: dict | None, fps: float) -> dict:
    """The composition with every layer's times in composition seconds (the input itself when nothing is timed)."""
    if not _any_timed(comp):
        return comp
    out = copy.deepcopy(comp)
    for layer in out.get("layers", []):
        _shift(layer, _offset(layer, 0.0, markers), fps, markers)
    return out


def offset_of(doc_data: dict, item_id: str, markers: dict | None) -> float:
    """Where an item's own time 0 sits in its composition's seconds: its marker's time, or its nearest timed
    parent's (0 when none). A key on a marker sits at that marker's time minus this, in the item's own seconds."""
    def walk(node: dict, off: float):
        for key in CHILDREN:
            for child in node.get(key, []):
                o = _offset(child, off, markers)
                if child.get("id") == item_id:
                    return o
                found = walk(child, o)
                if found is not None:
                    return found
        return None
    return next((o for c in doc_data.get("comps", []) if (o := walk(c, 0.0)) is not None), 0.0)


def placed(comp: dict, markers: dict | None) -> dict:
    """The composition as written (times counted from each layer's marker), except that every key on a marker has
    `t` in its owner's own seconds and keeps what was written in `ref` (a copy; the input when there is none)."""
    if not marked.names(comp):
        return comp
    out = copy.deepcopy(comp)

    def walk(node: dict, off: float):
        for key in CHILDREN:
            for child in node.get(key, []):
                o = _offset(child, off, markers)
                marked.resolve(child, markers, o)
                walk(child, o)
    walk(out, 0.0)
    return out
