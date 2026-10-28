"""Ground first (script.py): what a script makes stands on the ground unless it says otherwise. The one ground rule for
meshes, imports, groups and clay.

- A mesh, an import, a group or a combine made directly in the scene (not inside a group, not attached, not the
  ground or a backdrop) is grounded: its `y` is the height of its BASE (its lowest point at rest, time 0, as turned
  and scaled) above the ground's top; 0 (the default) stands it on the ground. Its y keys mean the same. `y_world=`
  instead puts its own origin (a shape's middle, an import's base, a group's origin) at that world height, as `y`
  used to: the rare floating thing. A group stands on the ground as a whole when its `with` block ends; what is inside
  a group stays in the group's space (its y is the group's y, as before).
- A clay made without a height (no at / y / draw / spin) is built where its numbers put it and, when the script ends,
  moves up or down so its lowest point is on the ground, with everything attached to it (script_figure.start).
- Placed by relation (place_on, row, start_in_view, cloth over=) means placed: the grounded `y` rule stops there.
Lights, cameras, shots and materials are never grounded. The ground's top is the `ground` item's y (0 in a new scene).
"""
from __future__ import annotations

import copy

from rostrum_core.tree import walk

from . import aim, clay_detail, item_bounds
from .kind import KIND
from .resolve import Frames

GROUNDED = ("mesh", "import", "group", "combine")
SKIP = ("light", "camera", "rig", "copies", "effector", "part")


def ground_top(b) -> float:
    for tree in (b.root, b.doc.data if b.doc is not None else {}):
        g = next((n for n in tree.get("items", []) if n.get("id") == "ground"), None)
        if g is not None:
            return float(g.get("y", 0.0))
    return 0.0


def wants(node: dict, top_level: bool) -> bool:
    """Whether a thing the script just made is grounded."""
    return (top_level and node["type"] in GROUNDED and node["id"] != "ground" and not node.get("backdrop")
            and not node.get("follow") and not node.get("stick") and not node.get("mirror"))


# --- how low a thing reaches when its own y is 0
def _points(fr: Frames, node: dict) -> list[list[float]]:
    kind, id_ = node["type"], node["id"]
    if kind in SKIP:
        return []
    if kind in ("group", "combine"):
        return [p for c in node.get("children", []) for p in _points(fr, c)]
    world = fr.world(id_, 0)
    if kind == "import":                                # read upright, its base on its origin (ops_import.read_file)
        return [aim.point(world, [0.0, 0.0, 0.0])]
    if kind == "clay":
        return [aim.point(world, p) for p in clay_detail.reach(node)]
    v = fr.values(id_, 0)
    if v.get("shape") == "sphere":                      # a ball's box turns with it; the ball doesn't reach lower
        c = aim.point(world, [0.0, 0.0, 0.0])
        r = v["radius"] * max(sum(row[k] ** 2 for row in world[0]) ** 0.5 for k in range(3))
        return [[c[0], c[1] - r, c[2]]]
    box = item_bounds._shape_box(v)
    if box is None:                                     # an editable mesh or an outline: the engine's built mesh
        try:
            box = item_bounds._built({"items": [node], "materials": [], "shots": []}, id_)
        except Exception:                               # no engine here: its origin is taken as its base
            box = None
    return [aim.point(world, c) for c in item_bounds._corners(*box)] if box else [aim.point(world, [0.0] * 3)]


def low_at_zero(node: dict) -> float:
    """The lowest point (world y, at rest, time 0) of a top-level thing whose own y were 0 and unkeyed."""
    probe = copy.deepcopy(node)
    probe["y"], probe["keys"] = 0.0, [k for k in probe.get("keys", []) if k.get("prop") != "y"]
    for k in ("aim", "follow", "stick"):
        probe.pop(k, None)                              # an aim at another thing: measured unaimed
    pts = _points(Frames({"items": [probe]}, range(0, 1), 1.0), probe)
    return min((p[1] for p in pts), default=0.0)


def settle(b, node: dict, y_given: bool):
    """Keep a grounded thing's base `y` above the ground: its own y (and y keys) carry the offset from its base to its
    origin, re-measured after every change (size, turn, scale, children). `y_given`: node["y"] was just set to a base."""
    offset = ground_top(b) - low_at_zero(node)
    old = b.grounded[node["id"]]
    node["y"] = round(float(node.get("y", 0.0)) + (offset if y_given else offset - old), 6) + 0.0
    for k in node.get("keys", []):                      # y keys hold the old offset (Item.key adds it)
        if k.get("prop") == "y" and offset != old:
            k["v"] = round(k["v"] + offset - old, 6) + 0.0
    b.grounded[node["id"]] = offset


def key_value(b, node: dict, prop: str, v):
    """A y key's value on a grounded thing: the base height given, plus its current offset."""
    return v + b.grounded[node["id"]] if prop == "y" and node["id"] in b.grounded else v


def release(b, id_: str):
    """Placed by relation from now on: its y is plain (the parent's space)."""
    b.grounded.pop(id_, None)


# --- a clay resting on the ground (script_figure.start's `grounded`)
def _low_points(step: dict) -> list[tuple[list[float], float]]:
    """(a point in the clay's own space, how far the surface reaches below it) for one joined piece."""
    if step.get("hidden") or step.get("step") != "piece" or step.get("mode", "add") != "add":
        return []
    shape, r = step.get("shape"), float(step.get("radius", 0.0))
    if shape == "sphere":
        return [(step["at"], r)]
    if shape == "capsule":
        return [(step["at"], r), (step["to"], r)]
    p = step.get("plane")
    if not p:
        return []
    o, u, v = p[:3], p[3:6], p[6:9]
    if shape == "outline":
        return [([o[i] + a * u[i] + b * v[i] for i in range(3)], 0.0) for a, b in step["outline"]]
    if shape == "spin":                             # a ring of radius r at height h along v: its lowest side
        side = max(0.0, 1.0 - v[1] * v[1]) ** 0.5
        return [([o[i] + h * v[i] for i in range(3)], r * side) for r, h in step["profile"]]
    return []


def rest_on_ground(b, node: dict):
    """Put the clay's lowest point (at rest, time 0) on the ground's top: it moves up or down, and so does everything
    attached to it (follow=<it>: attach_to=, place_on(it, at=)), so the parts stay where they were put on it."""
    if any(k.get("prop") == "y" for k in node.get("keys", [])) or node.get("rx") or node.get("rz"):
        return
    m = Frames(b.root, range(0, 1), 1.0).world(node["id"], 0)
    scale = abs(aim.det(m[0])) ** (1 / 3)
    low = [aim.point(m, p)[1] - reach * scale for st in node.get("steps", []) for p, reach in _low_points(st)]
    if not low:
        return
    dy = ground_top(b) - min(low)
    for n in [node, *(n for n in walk(b.root, KIND.lists) if n.get("follow") == node["id"])]:
        n["y"] = round(float(n.get("y", 0.0)) + dy, 6) + 0.0


def settle_clay(b, node: dict):
    """When the script ends: rest a clay made without a height on the ground."""
    if b.figures.get(node["id"], {}).get("ground"):
        rest_on_ground(b, node)
