"""Where a copy lands (layer.duplicate and layer.paste share this one rule): never exactly on top of a layer that
already sits there. A copy whose place is taken steps down and to the right by NUDGE comp px, and again for every
further copy, until its place is free. Pasting into another scene (or project) where nothing sits there stays in place."""
from __future__ import annotations

NUDGE = 24.0                                      # comp px per step, right and down


def _spot(item: dict):
    return (round(float(item.get("x", 0)), 3), round(float(item.get("y", 0)), 3))


def spots(siblings: list[dict]) -> set:
    """Where these layers sit, by type: what steps_for keeps clear (a caller copying many keeps it and adds each copy)."""
    return {(s.get("type"), *_spot(s)) for s in siblings}


def steps_for(siblings: list[dict], items: list[dict], taken: set | None = None) -> int:
    """How many NUDGE steps the copies need, all together (they keep their places among themselves), so none sits
    at the x, y of a sibling of its type. `taken`: spots(siblings), when the caller keeps it."""
    taken = spots(siblings) if taken is None else taken
    n = 0
    while any((i.get("type"), *(round(c + n * NUDGE, 3) for c in _spot(i))) in taken for i in items):
        n += 1
    return n


def stepped(item: dict, n) -> dict:
    """`item` (a copy the caller owns) moved by `n`: a number of NUDGE steps right and down, or a (dx, dy, turn, ratio)
    tuple (layer.duplicate's `by`, a copy's step from the one before): a layer's still x, y, rotation (added) and scale
    (times ratio); a key of those properties its value. A layer's keys are children of it: the caller passes the layer's
    step down to its keys only (`for_child`)."""
    if not n:
        return item
    dx, dy, turn, ratio = (n * NUDGE, n * NUDGE, 0, 1) if isinstance(n, (int, float)) else n
    if item.get("type") == "key":
        prop = item.get("prop")
        if prop in ("x", "y", "rotation", "scale") and "v" in item:
            item["v"] = round(_shift(prop, float(item["v"]), dx, dy, turn, ratio), 4)
        return item
    for k in ("x", "y", "rotation", "scale"):
        if k in item:
            item[k] = round(_shift(k, float(item[k]), dx, dy, turn, ratio), 4)
    return item


def _shift(prop, v, dx, dy, turn, ratio):
    return {"x": v + dx, "y": v + dy, "rotation": v + turn, "scale": v * ratio}[prop]


def for_child(child: dict, n: int) -> int:
    """The step a layer's child takes along: its keys follow the layer, layers inside a group stay put in it."""
    return n if child.get("type") == "key" else 0
