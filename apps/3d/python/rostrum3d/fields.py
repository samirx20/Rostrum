"""Every 3D item type's fields: the one table. The field operations, the inspector, the script layer's checks and
the compiler's defaults all read it (ENGINE_CONTRACT.md § 2: the core has no defaults table of its own). Each field
carries `valid_when` and `importance` (rule of individuality: a control that doesn't apply right now is absent).

Units: metres, degrees, seconds. Colours are #rrggbb (sRGB) here; the compiler makes them linear.
Animatable = every number and colour field, except those in STILL.
"""
from __future__ import annotations

import dataclasses

from rostrum_core import Param
from rostrum_core.conditions import holds

# The pieces, by job (this module stays the one import everyone uses):
from .field_kit import (ANIMATED, ANIMATING, ANY, C, CH, D, DOF, FOLLOWS, IS, N, NO_AIM, NOT, P, POLY, S, STEPS,  # noqa: F401
                        T, TIMING, TRANSFORM, X)
from .item_fields import COMBINE_OPS, FIELDS, SOLIDS  # noqa: F401
from .light_fields import KIND_DEFAULTS as LIGHT_KIND_DEFAULTS, KINDS as LIGHT_KINDS, STILL as LIGHT_STILL  # noqa: F401
from .mesh_fields import SHAPES  # noqa: F401

KIND_DEFAULTS = {"light": ("kind", LIGHT_KIND_DEFAULTS)}   # {item type: (its choice field, {choice: starting values})}
ITEMS = ("group", "mesh", "combine", "import", "light", "camera", "rig")      # scene items (USD prims)
KEYED = (*ITEMS, "bone")                       # what keys, poses and the animation operations can move (a bone: its Turn)
HOLDERS = ("group", "import", "rig", "combine")
LISTS = {"doc": ["items", "materials", "shots", "poses"], "group": ["children", "keys"],     # where child items live
         "import": ["children", "parts", "keys"], "mesh": ["bones", "keys"], "light": ["keys"], "camera": ["keys"],
         "combine": ["children", "keys"],
         "rig": ["children", "keys"],
         "bone": ["bones", "keys"]}                     # a chain: mesh › bone › bone … (ops_bones.py)
DATA_GROUPS = {"Mesh data", "Bone data"}       # data an operation writes (a mesh's points, a bone's head), never rows
STILL = {"mesh": {p.name for p in FIELDS["mesh"] if p.group == "Shape"},     # a mesh's shape is built once
         "light": LIGHT_STILL,
         "combine": {"op"},
         "bone": {"x", "y", "z", "length"},       # a bone moves only by its Turn
         "*": {"aim"}}
LABELS = {"group": "Group", "mesh": "Mesh", "combine": "Combine", "import": "Import", "part": "Part", "light": "Light", "camera": "Camera", "rig": "Camera rig",
          "material": "Material", "shot": "Shot", "key": "Key", "pose": "Pose",
          "bone": "Bone"}


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
    return [p.name for p in FIELDS[kind] if p.type in ("number", "color") and p.name not in still]


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
    return [n for n in given if (p := param(kind, n)) and not holds(p.valid_when, item, {"animated": True, "animating": True})]
