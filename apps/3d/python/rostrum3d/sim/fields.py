"""The Simulation fields (brief 25, SPEC §10): an item's group "Simulation" (what a body is made of and how it starts)
and a shot's (the ground, the stored result's key, and, brief 26a, Timing and Simplify read off the stored result).
Brief 26b: a shape (a `mesh` item) can also be Cloth, with Weight, Stiffness and Pinned edge (for_type gives a type
its own fields: only a mesh offers Cloth).

All of them are still (never keyed) and none is sent to the core as a prop (compile.RESOLVED): the simulation reads them
(sim/inputs.py). Only the item's `simulate` row shows while it is Off; the rest only while it Falls or Stays still.
"""
from __future__ import annotations

import dataclasses

from ..field_kit import ANY, CH, D, IS, N, S, T, X

KINDS = ["off", "falls", "still", "cloth"]
CLOTH_TYPES = ("mesh",)                           # what can be cloth: a shape (a plane drapes best; the core refines it)
PINS = ["none", "top", "bottom", "left", "right", "front", "back"]
SHAPES = ["exact", "box", "sphere"]
STARTS = ["moving", "asleep"]
TIMINGS = {"every": 1, "2s": 2, "3s": 3}        # Timing: each stored sample held this many frames (from the shot's start)
PLASTIC = 1100.0                                 # kg/m³: Mass from size, "as solid plastic"
TYPES = ("mesh", "combine", "import", "group", "clay", "copies")    # what can be a body (top-level only: sim/ops.py)

FALLS = IS("simulate", "falls")
BODY = ANY("simulate", "falls", "still")
CLOTH = IS("simulate", "cloth")
WORDS = {"off": "Off", "falls": "Falls", "still": "Stays still", "cloth": "Cloth"}


def _simulate(kinds: list[str]):
    return dataclasses.replace(
        CH("simulate", kinds, "Simulate", "Simulation", "off", S,
           help="Falls: moved by gravity and bumps. Stays still: others land on it and bounce off it, it never moves. "
                + ("Cloth: drapes and folds over what is under it. " if "cloth" in kinds else "")
                + "Off: not part of the simulation"),
        labels={k: WORDS[k] for k in kinds})


ITEM = [
    _simulate([k for k in KINDS if k != "cloth"]),
    T("massFromSize", "Mass from size", "Simulation", True, S, FALLS,
      help="Weighs what it would if it were solid plastic of its size"),
    N("mass", "Mass", "Simulation", 0.001, 10000, 0.001, "kg", S, {"all": [FALLS, IS("massFromSize", False)]},
      default=0.1),
    N("bounce", "Bounce", "Simulation", 0, 1, 0.01, "", S, BODY, default=0.2,
      help="0 lands dead, 1 bounces back as high as it fell"),
    N("friction", "Friction", "Simulation", 0, 2, 0.01, "", S, ANY("simulate", "falls", "still", "cloth"), default=0.6,
      help="0 slides like ice, 1 grips like rubber"),
    dataclasses.replace(
        CH("starts", STARTS, "Starts", "Simulation", "moving", S, FALLS,
           help="Asleep until hit: it stays where it is until something knocks it"),
        labels={"moving": "Moving", "asleep": "Asleep until hit"}),
    N("fallStart", "Falls from", "Simulation", 0, 3600, 0.01, "s", S, FALLS, default=0.0,
      help="Holds still where it is until this many seconds into the shot (others land on it and bounce off it), "
           "then falls. 0: from the shot's start"),
    dataclasses.replace(                           # "simShape": a mesh's own `shape` (box, sphere …) is taken
        CH("simShape", SHAPES, "Shape", "Simulation", "exact", D, BODY,
           help="How it collides. Exact: its own outline (for one that falls, the outline with the dents filled); "
                "Box or Sphere: faster, rougher"),
        labels={"exact": "Exact", "box": "Box", "sphere": "Sphere"}),
]
CLOTH_ITEM = [
    N("clothWeight", "Weight", "Simulation", 0.01, 5, 0.01, "kg/m²", S, CLOTH, default=0.2,
      help="How heavy a square metre of it is: silk 0.05, cotton 0.2, denim 0.4, felt or leather 1"),
    N("stiffness", "Stiffness", "Simulation", 0, 1, 0.01, "", S, CLOTH, default=0.3,
      help="0 folds like silk, 1 bends like thin card"),
    dataclasses.replace(
        CH("pinned", PINS, "Pinned edge", "Simulation", "none", S, CLOTH,
           help="The points along that side (as seen in the scene at the first frame) are held in place, like a "
                "curtain on its rail"),
        labels={"none": "None", "top": "Top", "bottom": "Bottom", "left": "Left", "right": "Right", "front": "Front",
                "back": "Back"}),
]
NAMES = {p.name for p in ITEM} | {p.name for p in CLOTH_ITEM}


def for_type(type_: str) -> list:
    """The item fields a type gets: a shape (mesh) can also be Cloth, with its own three rows."""
    if type_ not in CLOTH_TYPES:
        return ITEM
    return [_simulate(KINDS), *ITEM[1:], *CLOTH_ITEM]

KEY = "simKey"
SHOT = [
    T("simGround", "Ground", "Simulation", True, S,
      help="A floor at height 0 that falling things land on, even with nothing modelled there"),
    dataclasses.replace(X(KEY, "Stored result", "Simulation data", "", D,
                          help="The key of this shot's last stored simulation result (sim.run sets it; empty = never computed)"),
                        shown="script"),
    dataclasses.replace(
        CH("simTiming", list(TIMINGS), "Timing", "Simulation", "every", S,
           help="On 2s / On 3s: the simulated things move in steps, like hand animation, while the camera stays smooth"),
        labels={"every": "Every frame", "2s": "On 2s", "3s": "On 3s"}),
    N("simSimplify", "Simplify", "Simulation", 1, 12, 1, "", S, integer=True, default=1,
      help="Keeps every nth frame of the result and moves smoothly between them (1 = every frame)"),
]
SHOT_NAMES = {p.name for p in SHOT}
