"""Every 3D item type's fields: the one table. The field operations, the inspector, the script layer's checks and
the compiler's defaults all read it (ENGINE_CONTRACT.md § 2: the core has no defaults table of its own). Each field
carries `valid_when` and `importance` (rule of individuality: a control that doesn't apply right now is absent).

Units: metres, degrees, seconds. Colours are #rrggbb (sRGB) here; the compiler makes them linear.
Animatable = every number and colour field, except those in STILL, and the toggles in KEYED_TOGGLES (Visible): a
toggle key holds v = 1 (on) or 0 (off) and always holds until the next key, whatever its ease (toggle_at).
"""
from __future__ import annotations

import dataclasses

from rostrum_core import Param
from rostrum_core.conditions import holds
from rostrum_core.keys import track_value

# The pieces, by job (this module stays the one import everyone uses):
from .field_kit import (ANIMATED, ANIMATING, ANY, C, CH, D, DOF, FOLLOWS, IS, N, NO_AIM, NOT, P, POLY, S, STEPS,  # noqa: F401
                        T, TIMING, TRANSFORM, X)
from .item_fields import COMBINE_OPS, FIELDS, SOLIDS  # noqa: F401
from .clay_fields import STILL as CLAY_STILL
from .copies_fields import STILL as COPIES_STILL
from .light_fields import KIND_DEFAULTS as LIGHT_KIND_DEFAULTS, KINDS as LIGHT_KINDS, STILL as LIGHT_STILL  # noqa: F401
from .mesh_fields import SHAPE_DEFAULTS, SHAPES  # noqa: F401
from .sim import fields as SIM

KIND_DEFAULTS = {"light": ("kind", LIGHT_KIND_DEFAULTS), "mesh": ("shape", SHAPE_DEFAULTS)}   # {item type: (its choice field, {choice: starting values})}
ITEMS = ("group", "mesh", "combine", "import", "light", "camera", "rig", "clay", "copies")      # scene items (USD prims)
KEYED = (*ITEMS, "effector", "bone", "claylayer")                       # what keys, poses and the animation operations can move (a bone: its Turn)
HOLDERS = ("group", "import", "rig", "combine", "copies")
LISTS = {"doc": ["items", "materials", "shots", "poses", "collections", "recipes"], "group": ["children", "keys"],     # where child items live
         "import": ["children", "parts", "keys"], "mesh": ["bones", "keys", "paints", "paintmasks"], "light": ["keys"],
         "camera": ["keys"],
         "clay": ["steps", "sculptLayers", "bones", "keys", "paints", "paintmasks"],   # its steps build its shape, in order (clay_fields.py); its joints (ops_pose.py)
         "combine": ["children", "keys"],
         "copies": ["children", "keys"],               # its source item(s) and its effectors
         "effector": ["keys"],
         "claylayer": ["keys"],                        # a sculpt layer's Amount keyed: a face shape (clay_faces.py)
         "rig": ["children", "keys"],
         "bone": ["bones", "keys"]}                     # a chain: mesh › bone › bone … (ops_bones.py); a mesh paints (paint_fields.py)
DATA_GROUPS = {"Mesh data", "Bone data", "Mirror data", "Simulation data"}   # data an operation writes (a mesh's points, a bone's head, a mirrored copy's link), never rows
STILL = {"mesh": {p.name for p in FIELDS["mesh"] if p.group in ("Shape", "Paint")},   # a mesh's shape is built once
         "light": LIGHT_STILL,
         "combine": {"op"},
         **COPIES_STILL,
         "clay": CLAY_STILL,                     # its brush settings and detail
         "bone": {"x", "y", "z", "length"},       # a bone moves only by its Turn
         "*": {"aim"}}
for _type in SIM.TYPES:                          # the Simulation group is never keyed (sim/fields.py)
    STILL[_type] = STILL.get(_type, set()) | SIM.NAMES
LABELS = {"group": "Group", "mesh": "Mesh", "combine": "Combine", "import": "Import", "part": "Part", "light": "Light", "camera": "Camera", "rig": "Camera rig",
          "material": "Material", "shot": "Shot", "key": "Key", "pose": "Pose",
          "bone": "Bone", "collection": "Collection", "recipe": "Recipe", "clay": "Clay", "copies": "Copies", "effector": "Change near", "claystep": "Clay step", "claylayer": "Sculpt layer"}
KEYED_TOGGLES = {"visible"}                    # toggles keys may drive: on / off at each key, nothing in between


def param(kind: str, name: str) -> Param | None:
    return next((p for p in FIELDS.get(kind, ()) if p.name == name), None)


def defaults(kind: str, values: dict | None = None) -> dict:
    """A new item's starting values; `values` (what it is made with) picks a kind's own ones (a spot's small bulb)."""
    out = {p.name: p.default for p in FIELDS[kind]}
    choice, table = KIND_DEFAULTS.get(kind, ("", {}))
    return {**out, **table.get((values or {}).get(choice, out.get(choice)), {})}


def animatable(kind: str) -> list[str]:
    if kind not in KEYED:
        return []
    still = STILL.get(kind, set()) | STILL["*"]
    return [p.name for p in FIELDS[kind] if (p.type in ("number", "color") or p.name in KEYED_TOGGLES and p.type == "toggle")
            and p.name not in still]


def is_toggle(kind: str, name: str) -> bool:
    """A keyable on / off field (Visible): its keys hold v 1 or 0 and its value is True or False."""
    return name in KEYED_TOGGLES and (p := param(kind, name)) is not None and p.type == "toggle"


def toggle_at(keys: list[dict], t: float) -> bool:
    """A toggle's value at t from its sorted keys: the last key's at or before t (the first key's before it), never
    in between, whatever ease a key carries; a key's v of 0.5 or more is on. A key counts from its frame: key times
    are kept to 0.0001 s (lip sync's 1.5417 is frame 37 at 24 fps, 1.541666… s), so it is read 0.0001 s late."""
    return float(track_value([{**k, "ease": "hold"} for k in keys], t + 1e-4)) >= 0.5


def key_value_at(kind: str, name: str, keys: list[dict], t: float):
    """A keyed field's value at t: a toggle's on / off (toggle_at), else the shared evaluator's."""
    return toggle_at(keys, t) if is_toggle(kind, name) else track_value(keys, t)


def unconditional(kind: str) -> list[Param]:
    """The fields as arguments of an add operation: no valid_when (checked on the whole new item, `not_valid`)."""
    return [dataclasses.replace(p, valid_when=None) for p in FIELDS[kind]]


def animated_fact(item: dict) -> bool:
    """The item or anything inside it has keys: its Timing then shows (the `animated` fact, kind.py)."""
    stack = [item]
    while stack:
        it = stack.pop()
        if it.get("keys"):
            return True
        stack += it.get("children", []) + it.get("bones", [])
    return False


def not_valid(kind: str, item: dict, given) -> list[str]:
    """The given field names that don't apply to `item` as it is (e.g. width on a sphere). Timing may be given before
    the keys are (a script's mesh(…, timing="on2") then .key(…)): `animated` only decides whether screens show it."""
    return [n for n in given if (p := param(kind, n)) and not holds(p.valid_when, item, {"animated": True, "animating": True, "sculpting": True})]
