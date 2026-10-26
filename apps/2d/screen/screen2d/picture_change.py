"""Does a drag's step change the canvas picture at the playhead? A bar slid or trimmed, or a key moved, often leaves
what the playhead shows exactly as it was (the layer is off-screen at that time both before and after, the value at
that time is the same): then the engine is not asked again. Read from what the step touched (rostrum_gui/touched.py,
the one "what did this preview change"), comparing each touched layer, with everything inside it, as the picture
shows it at the playhead: its own fields (times aside), its animated values there and whether it is on at all.

Anything it can't vouch for counts as a change, and the picture is drawn: an add, remove or move; a touch outside a
layer (the scene's own settings); motion blur (the picture spans a moment, not an instant); an expression anywhere
(it may read any layer); a layer riding or following a touched path; content that plays in time (video, drawings,
3D renders: their start says which picture shows). No Qt.
"""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum2d.evaluate import value_at
from rostrum_core.keys import animated
from rostrum2d.retime import END_OF_COMP
from rostrum2d.subtree import Subtree

TIMELESS = {"shape", "text", "image", "path", "group", "camera"}   # their start / end only say whether they show
FOLLOWS = ("ridePath", "pathLayer")                                 # fields that name a path layer to follow


def changes(before, after, touched, t: float, lists: dict, blur: bool) -> bool:
    """`before`, `after`: (placed comp, its index) the picture was last asked for and now; `touched`: the step's."""
    if touched is None or touched.structural or blur or before is None:
        return True
    (comp0, idx0), (comp1, idx1) = before, after
    layers = set()
    for i in touched.ids:
        lay = _layer_of(idx1, i)
        if lay is None or _layer_of(idx0, i) != lay:
            return True
        layers.add(lay)
    if _reads_others(comp1, layers, lists):
        return True
    return any(_seen(idx0[lay].item, t, lists) != _seen(idx1[lay].item, t, lists) for lay in layers)


def _layer_of(idx, item_id):
    """The nearest layer holding the item (itself if it is one); None outside any layer."""
    loc = idx.get(item_id)
    while loc is not None:
        if loc.item.get("type") in F.LAYERS:
            return loc.item["id"]
        loc = idx.get(loc.parent) if loc.parent else None
    return None


def _reads_others(comp, layers, lists) -> bool:
    """An expression anywhere, or a layer following one of `layers` as its path."""
    found = _reads(lists)(comp)
    return "@expr" in found or any(lay in found for lay in layers)


_READS = {}


def _reads(lists):
    """What a subtree reads of others (remembered per item: subtree.py): "@expr" for an expression, the path layers
    followed by name."""
    key = id(lists)
    if key not in _READS:
        _READS[key] = (lists, Subtree(
            lambda item: (["@expr"] if item.get("exprs") else []) + [item[f] for f in FOLLOWS if item.get(f) and isinstance(item[f], str)],
            lambda item: (c for key in lists.get(item.get("type"), ()) if key != "keys" for c in item.get(key, ()))))
    return _READS[key][1]


def _seen(item, t, lists):
    """The item as the picture at `t` shows it, with what is inside it."""
    own = {k: v for k, v in item.items() if k not in lists.get(item["type"], ())}
    if item["type"] in TIMELESS and not any(item.get(f) for f in FOLLOWS):
        start, end = own.pop("start", 0.0), own.pop("end", END_OF_COMP)
        if not start <= t < end:
            return "off"                            # not in the picture at all: nothing else of it counts
    if item.get("keys") and item["type"] in F.ANIMATED_OWNERS:
        own["@at"] = {p: value_at(item, p, t) for p in sorted(animated(item))}
    inside = tuple(_seen(c, t, lists) for key in lists.get(item["type"], ()) if key != "keys" for c in item.get(key, ()))
    return own, inside
