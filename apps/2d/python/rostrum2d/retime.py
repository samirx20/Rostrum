"""Layers timed from a shared marker: the one place a layer's own times become composition times.

A layer whose `marker` names a shared marker ("logo lands") counts its times from that marker: its `start`, `end`,
keys, and those of everything inside it (effects, masks, child layers, a gradient's stops, a rig's bones, a drawing's
frames). Move the
marker in any app and the whole layer moves with it (AGENTS.md rule 8: cross-app timing by named markers, never
copied numbers). A layer inside a timed group with a `marker` of its own counts from its own marker. `endMarker` ends a layer on
another marker ("the phone shot ends on reveal"); `start` may be below 0 (a lead-in before its marker). A child left at
Starts at 0 starts with its group, so a group's lead-in shows its children too (`_start`: the one rule).

A key may be timed on a marker of its own (`"t": "#drop+0.2"`, rostrum_core.keys.marked): it lands at that moment
of the project, whatever its layer counts from, before the layer's start too (a pre-roll); `offset_of` says where
an item's own time 0 sits, and `placed` gives the composition as written with those keys in their owner's seconds
(the timeline and curve editor read that).

`timed(comp, markers, fps)` returns the composition with every time in composition seconds (copy on write: only
the items whose times change are copies, the rest stay the document's own objects); the scene description and the motion facts read that, so preview, export and the look tools agree.
The document keeps the times as written (from the marker). A marker that isn't in the project fails loudly.
"""
from __future__ import annotations

import copy

from rostrum_core.errors import RostrumError, codes
from rostrum_core.keys import marked
from rostrum_core.marker_times import lookup

from . import fields as F
from .subtree import Subtree

FIELD, END = "marker", "endMarker"
# every list whose items have keys of their own (kind.LISTS): one left out keeps "#marker" key times unresolved
CHILDREN = ("effects", "masks", "layers", "bones", "iks", "binds", "stops")
END_OF_COMP = 36000.0               # `end`'s "End of comp" word (fields.py): stays the end of the comp


_TIMED = Subtree(lambda node: ("timed",) if node.get(FIELD) or node.get(END) or any(marked.marked(k) for k in node.get("keys", ())) else (),
                 lambda node: (c for key in CHILDREN for c in node.get(key, ())))   # remembered per item: a drag's move asks again


def _any_timed(node: dict) -> bool:
    return bool(_TIMED(node))


def _at(item: dict, field: str, markers: dict | None) -> float:
    name = item[field]
    at = lookup(markers or {}, name)            # names match as keys' markers do: case and spaces ignored
    if at is None:
        raise RostrumError(codes.NOT_FOUND, f'{item["id"]}.{field}', f'marker "{name}"', "is not in the project",
                           hint=f'Markers: {", ".join(sorted(markers or {})) or "none"}. Add it (edit_markers) or clear the field.')
    return float(at)


def _offset(item: dict, inherited: float, markers: dict | None) -> float:
    return _at(item, FIELD, markers) if item.get(FIELD) else inherited


def _start(item: dict, off: float, lead: float | None) -> float:
    """When a layer starts, in composition seconds: its own `start` counted from its time 0 (`off`). A child left at
    0 (the default: "from the start") that has no marker of its own starts with its parent (`lead`, the parent's
    start in composition seconds) when the parent starts earlier: a group's lead-in before its marker shows its
    children too, as look_motion, look_frame and the export all read it."""
    own = float(item.get("start", 0.0))
    if lead is not None and own == 0.0 and not item.get(FIELD) and lead < off:
        return lead
    return own + off


def _shifted(item: dict, off: float, fps: float, markers: dict | None, lead: float | None = None) -> dict:
    """The item with its times in composition seconds: the item itself when none of them changes, else a copy of just
    what changes (copy on write: what a layer timed from a marker doesn't touch stays the document's own object).
    `lead`: the parent's start in composition seconds (None at the top or when the parent isn't shifted)."""
    layer = F.param(item["type"], "start") is not None      # layers (effects, masks and bones have no start)
    start = _start(item, off, lead) if off and layer else None
    kids = {key: [_shifted(c, _offset(c, off, markers), fps, markers, start) for c in item[key]] for key in CHILDREN if item.get(key)}
    kids = {key: new for key, new in kids.items() if any(a is not b for a, b in zip(new, item[key]))}
    keys = item.get("keys", [])
    marks = any(marked.marked(k) for k in keys)
    if not (kids or off or item.get(END) or marks):
        return item
    out = {**item, **kids}
    if item.get(END):                  # ends on a marker: that moment, whatever the layer counts from
        out["end"] = _at(item, END, markers) - off
    if keys and (off or marks):        # a key on a marker: that moment; the others count from the layer's
        out["keys"] = [dict(k) if marked.marked(k) else {**k, "t": k["t"] + off} for k in keys]
        marked.resolve(out, markers)   # (on the copies)
    if not off:
        return out
    if start is not None:
        out["start"] = start
    if out.get("end", END_OF_COMP) < END_OF_COMP:
        out["end"] = out["end"] + off
    if item.get("frames"):             # a drawing's frames are composition frame numbers
        out["frames"] = [{**f, "at": f["at"] + round(off * fps)} for f in item["frames"]]
    return out


def timed(comp: dict, markers: dict | None, fps: float, memo: dict | None = None) -> dict:
    """The composition with every layer's times in composition seconds (the input itself when nothing is timed; else
    a copy of only what changes). `memo` (scene_keep.py, for one set of markers): {layer id: (layer, fps, timed)}
    kept between calls, so an unchanged timed layer comes back as the same object."""
    if not _any_timed(comp):
        if memo is not None:
            memo.clear()
        return comp
    seen, layers = {}, []
    for layer in comp.get("layers", []):
        got = memo.get(layer["id"]) if memo is not None else None
        if got is None or got[0] is not layer or got[1] != fps:
            got = (layer, fps, _shifted(layer, _offset(layer, 0.0, markers), fps, markers))
        seen[layer["id"]] = got
        layers.append(got[2])
    if memo is not None:
        memo.clear()
        memo.update(seen)
    return {**comp, "layers": layers} if "layers" in comp else comp


_offsets = [(None, None, None)]   # [(document data, markers, {item id: offset})]: a screen asks per settings row and per moved layer


def offset_of(doc_data: dict, item_id: str, markers: dict | None) -> float:
    """Where an item's own time 0 sits in its composition's seconds: its marker's time, or its nearest timed
    parent's (0 when none). A key on a marker sits at that marker's time minus this, in the item's own seconds.
    Kept per document state and markers (each change gives new ones): one walk of the whole document gives every
    item's, so a drag of 200 layers walks once per step, not once per layer."""
    got = _offsets[0]                       # (one read and one write of the cell: a worker thread may ask too)
    if got[0] is not doc_data or got[1] is not markers:
        got = _offsets[0] = (doc_data, markers, _offset_walk(doc_data, markers))
    off = got[2].get(item_id, 0.0)
    if isinstance(off, RostrumError):       # its own or a parent's marker is missing: said when asked, as before
        raise off
    return off


def _offset_walk(doc_data: dict, markers: dict | None) -> dict:
    """{item id: offset} for every item inside the compositions (the error, for an item timed by a missing marker)."""
    out = {}

    def walk(node: dict, off):
        for key in CHILDREN:
            for child in node.get(key, []):
                try:
                    o = _offset(child, off, markers)        # (a parent's error passes down unless it has its own marker)
                except RostrumError as err:
                    o = err
                if "id" in child:
                    out.setdefault(child["id"], o)
                walk(child, o)
    for c in doc_data.get("comps", []):
        walk(c, 0.0)
    return out


def as_played(doc_data: dict, item_id: str, markers: dict | None) -> tuple[dict, dict] | None:
    """(the item with its times in composition seconds, its composition), or None when no composition holds it:
    the same `_shifted` the render reads (only the top layer holding it), so a link can't disagree with the frames."""
    def find(node: dict):
        for key in CHILDREN:
            for child in node.get(key, []):
                got = child if child.get("id") == item_id else find(child)
                if got is not None:
                    return got
        return None
    for comp in doc_data.get("comps", []):
        for top in comp.get("layers", []):
            if find({"layers": [top]}) is not None:
                fps = comp.get("fps", F.defaults("comp")["fps"])
                return find({"layers": [_shifted(top, _offset(top, 0.0, markers), fps, markers)]}), comp
    return None


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
