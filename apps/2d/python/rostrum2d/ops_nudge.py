"""Where a copy lands (layer.duplicate and layer.paste share this one rule): never exactly on top of a layer that
already sits there. A copy whose place is taken steps down and to the right by NUDGE comp px, and again for every
further copy, until its place is free. Pasting into another scene (or project) where nothing sits there stays in place."""
from __future__ import annotations

NUDGE = 24.0                                      # comp px per step, right and down


def _spot(item: dict):
    return (round(float(item.get("x", 0)), 3), round(float(item.get("y", 0)), 3))


def steps_for(siblings: list[dict], items: list[dict]) -> int:
    """How many NUDGE steps the copies need, all together (they keep their places among themselves), so none sits
    at the x, y of a sibling of its type."""
    taken = {(s.get("type"), *_spot(s)) for s in siblings}
    n = 0
    while any((i.get("type"), *(round(c + n * NUDGE, 3) for c in _spot(i))) in taken for i in items):
        n += 1
    return n


def stepped(item: dict, n: int) -> dict:
    """`item` (a copy the caller owns) moved n steps: a layer's still x, y; a key of x or y its value. A layer's keys
    are children of it: the caller passes the layer's step down to its keys only (`for_child`)."""
    if n:
        if item.get("type") == "key":
            if item.get("prop") in ("x", "y") and "v" in item:
                item["v"] = round(float(item["v"]) + n * NUDGE, 4)
            return item
        for k in ("x", "y"):
            if k in item:
                item[k] = round(float(item[k]) + n * NUDGE, 4)
    return item


def for_child(child: dict, n: int) -> int:
    """The step a layer's child takes along: its keys follow the layer, layers inside a group stay put in it."""
    return n if child.get("type") == "key" else 0
