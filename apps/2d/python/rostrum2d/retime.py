"""Layers timed from a shared marker: the one place a layer's own times become composition times.

A layer whose `marker` names a shared marker ("logo lands") counts its times from that marker: its `start`, `end`,
keys, and those of everything inside it (effects, masks, child layers, a rig's bones, a drawing's frames). Move the
marker in any app and the whole layer moves with it (AGENTS.md rule 8: cross-app timing by named markers, never
copied numbers). A layer inside a timed group with a `marker` of its own counts from its own marker. `endMarker` ends a layer on
another marker ("the phone shot ends on reveal"); `start` may be below 0 (a lead-in before its marker).

`timed(comp, markers, fps)` returns the composition with every time in composition seconds (a copy, only when some
layer is timed); the scene description and the motion facts read that, so preview, export and the look tools agree.
The document keeps the times as written (from the marker). A marker that isn't in the project fails loudly.
"""
from __future__ import annotations

import copy

from rostrum_core.errors import RostrumError, codes

from . import fields as F

FIELD, END = "marker", "endMarker"
CHILDREN = ("effects", "masks", "layers", "bones", "iks", "binds")
END_OF_COMP = 36000.0               # `end`'s "End of comp" word (fields.py): stays the end of the comp


def _any_timed(node: dict) -> bool:
    return bool(node.get(FIELD) or node.get(END)) or any(_any_timed(c) for key in CHILDREN for c in node.get(key, []))


def _at(item: dict, field: str, markers: dict | None) -> float:
    name = item[field]
    if not markers or name not in markers:
        raise RostrumError(codes.NOT_FOUND, f'{item["id"]}.{field}', f'marker "{name}"', "is not in the project",
                           hint=f'Markers: {", ".join(sorted(markers or {})) or "none"}. Add it (edit_markers) or clear the field.')
    return float(markers[name])


def _offset(item: dict, inherited: float, markers: dict | None) -> float:
    return _at(item, FIELD, markers) if item.get(FIELD) else inherited


def _shift(item: dict, off: float, fps: float, markers: dict | None) -> None:
    for key in CHILDREN:
        for child in item.get(key, []):
            _shift(child, _offset(child, off, markers), fps, markers)
    if item.get(END):                  # ends on a marker: that moment, whatever the layer counts from
        item["end"] = _at(item, END, markers) - off
    if not off:
        return
    for k in item.get("keys", []):
        k["t"] = k["t"] + off
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
