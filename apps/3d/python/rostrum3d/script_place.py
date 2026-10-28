"""Placing by relation in a script (script.py's place_on and row), by the things' real room in the world (item_bounds:
turned, scaled, inside groups), at rest (time 0). A move is written into each thing's own parent space, so a thing in
a group stays in it.

- `a.place_on(b)`: a's base on b's top, over b's middle (+ `gap` metres between them).
- `a.place_on(b, beside="left")` or `a.place_on(beside=b, side="left")`: a next to b on that side, `gap` metres
  between their boxes, lined up with b's middle along the other level axis, a's base level with b's (on the same
  table as b).
  `a.place_on(in_front_of=b)` is side "front". Sides are the world's, not the picture's: left = −X, right = +X,
  front = +Z (towards the start camera), back = −Z.
- `row([a, b, c], gap=0.1, centre=True, axis="x", at=None)`: side by side along x (or z) in the order given, `gap`
  metres between boxes, the row's middle on 0 (or `at`: a number, or a point (x, y, z) whose level coordinates the
  row is centred on; centre=False starts the row there), each lined up across the row and standing on the ground.
"""
from __future__ import annotations

from . import aim, item_bounds, script_ground
from .resolve import Frames

SIDES = {"left": (0, -1), "right": (0, 1), "front": (2, 1), "back": (2, -1)}
AXES = {"x": 0, "z": 2}


def _scene(b) -> dict:
    from .script_figure import _scene
    return _scene(b)


def box(data: dict, id_: str, who: str):
    try:
        return item_bounds.world_box(data, [id_], 0.0)
    except (ValueError, KeyError) as e:
        raise ValueError(f"{who}: can't measure {id_!r}: {e}") from None


def move(data: dict, node: dict, delta):
    """Move a thing by a world vector, written in its parent's space."""
    fr = Frames(data, range(0, 1), 1.0)
    parent = fr.parent.get(node["id"])
    pw = fr.world(parent, 0) if parent else aim.IDENTITY
    inv = aim.invert(pw)
    zero = aim.point(inv, [0.0, 0.0, 0.0])
    local = [a - z for a, z in zip(aim.point(inv, list(delta)), zero)]
    for k, d in zip("xyz", local):
        if abs(d) > 1e-12:
            node[k] = round(float(node.get(k, 0.0)) + d, 6) + 0.0


def place(b, node: dict, other, beside=None, side=None, in_front_of=None, gap: float = 0.0):
    """place_on without at= (see the module's note)."""
    who = f"{node['id']}.place_on"
    if in_front_of is not None:
        other, side = in_front_of, "front"
    elif isinstance(beside, str) and beside in SIDES:
        side = beside
    elif beside is not None:
        other = beside
    if other is None:
        raise ValueError(f"{who}: name what it goes on or beside: place_on(other), place_on(other, beside=\"left\"), "
                         "place_on(in_front_of=other)")
    if (beside is not None or in_front_of is not None) and side not in SIDES:
        raise ValueError(f"{who}: side {side!r}: say one of {', '.join(SIDES)} (the world's sides; front = +Z)")
    oid = getattr(other, "id", other)
    data = _scene(b)
    if oid not in {n["id"] for n in _all(data)}:
        raise ValueError(f"{who}: {oid!r} is not in the scene or made earlier in the script")
    (olo, ohi), (lo, hi) = box(data, oid, who), box(data, node["id"], who)
    mid, omid = [(a + c) / 2 for a, c in zip(lo, hi)], [(a + c) / 2 for a, c in zip(olo, ohi)]
    if side is None or (beside is None and in_front_of is None):     # on top
        script_ground.release(b, node["id"])
        delta = [omid[0] - mid[0], ohi[1] + gap - lo[1], omid[2] - mid[2]]
    else:
        k, sign = SIDES[side]
        other_k = 2 - k
        edge = ohi[k] + gap - lo[k] if sign > 0 else olo[k] - gap - hi[k]
        script_ground.release(b, node["id"])
        delta = [0.0, olo[1] - lo[1], 0.0]                     # its base level with the other's: on the same surface
        delta[k], delta[other_k] = edge, omid[other_k] - mid[other_k]
    move(data, node, delta)


def row(b, nodes: list[dict], gap: float = 0.1, centre: bool = True, axis: str = "x", at=None):
    if axis not in AXES:
        raise ValueError(f'row: axis {axis!r}: "x" (left to right) or "z" (back to front)')
    if not nodes:
        raise ValueError("row: give the things to line up, e.g. row([a, b, c], gap=0.1)")
    k, across = AXES[axis], 2 - AXES[axis]
    point = [0.0, 0.0, 0.0] if at is None else ([float(at)] * 3 if isinstance(at, (int, float)) else [float(c) for c in at])
    data = _scene(b)
    boxes = [box(data, n["id"], "row") for n in nodes]
    length = sum(hi[k] - lo[k] for lo, hi in boxes) + gap * (len(nodes) - 1)
    start = point[k] - (length / 2 if centre else 0.0)
    top = script_ground.ground_top(b)
    for n, (lo, hi) in zip(nodes, boxes):
        delta = [0.0, top - lo[1], 0.0]
        delta[k], delta[across] = start - lo[k], point[across] - (lo[across] + hi[across]) / 2
        move(data, n, delta)
        start += hi[k] - lo[k] + gap


def _all(data: dict):
    stack = list(data.get("items", []))
    while stack:
        n = stack.pop()
        yield n
        stack += n.get("children", [])
