"""A clay's fields and its steps' fields (item_fields.py takes them in). A clay is a lump you sculpt: its shape is
its `steps`, applied in order by the core (pieces: spheres and capsules joined or carved; strokes: brush dabs).
Its Brush group holds the *next* stroke's settings, so screens show them from field data; each stroke step keeps its
own copy. All positions are in the clay's own space, in metres. Dab files: clay_dabs.py; the scene: clay_scene.py.
"""
from __future__ import annotations

import dataclasses

from rostrum_core import Param

from .field_kit import CH, D, IS, N, S, SCULPTING, T, TRANSFORM, X

BRUSHES = ["add", "carve", "smooth", "pull", "flatten", "crease"]     # the core has all six; CL1's screen shows three
SYMMETRY = ["off", "x"]
_MIRROR = {"off": "Off", "x": "Left–right"}
PIECE, STROKE = IS("step", "piece"), IS("step", "stroke")

CLAY = [
    CH("brush", BRUSHES, "Brush", "Brush", "add", when=SCULPTING,
       help="Add builds clay up, Carve digs in, Smooth evens bumps out; Pull drags the surface along the stroke, "
            "Flatten presses it to a plane, Crease cuts a sharp fold"),
    N("brushSize", "Size", "Brush", 0.0005, 10, 0.001, "m", when=SCULPTING, default=0.03, help="The brush's radius"),
    dataclasses.replace(N("brushStrength", "Strength", "Brush", 0, 1, 0.01, "", when=SCULPTING, default=0.5),
                        display="percent"),
    dataclasses.replace(CH("symmetry", SYMMETRY, "Mirror", "Brush", "x", when=SCULPTING,
                           help="Left–right: every stroke and piece is mirrored across the clay's own X = 0"),
                        labels=_MIRROR),
    T("accumulate", "Build up", "Brush", False, S, SCULPTING,
      help="On: going over the same place keeps adding. Off: one stroke adds at most its strength, however often "
           "it passes"),
    N("detail", "Detail", "Clay", 0.0002, 0.05, 0.0001, "m", D, default=0.002,
      help="How fine the clay is: the size of its smallest grain. Smaller = finer, slower and more memory"),
    X("material", "Material", "Material", "", help='A material id, or "" for none', refers="material"),
] + TRANSFORM

_V3 = lambda name, label, when, help: Param.list(name, "number", label=label, group="Step data", importance=D,  # noqa: E731
                                                 valid_when=when, min=-1e5, max=1e5, min_items=3, max_items=3,
                                                 default=None, nullable=True, help=help)

STEP = [
    CH("step", ["piece", "stroke"], "Step", "Step", "piece", D, help="A piece (a sphere or capsule) or a brush stroke"),
    X("name", "Name", "Step", "", S, help='A word for the step ("body", "nose"); optional'),
    # a piece
    CH("shape", ["sphere", "capsule"], "Shape", "Piece", "sphere", when=PIECE),
    _V3("at", "At", PIECE, "Its centre (a capsule: one end), in the clay's own space"),
    _V3("to", "To", {"all": [PIECE, IS("shape", "capsule")]}, "A capsule's other end"),
    N("radius", "Radius", "Piece", 0.0001, 100, 0.001, "m", when=PIECE, default=0.1),
    CH("mode", ["add", "carve"], "Mode", "Piece", "add", when=PIECE, help="Add joins it on; Carve cuts it out"),
    N("blend", "Blend", "Piece", 0, 100, 0.001, "m", S, PIECE, default=0.0,
      help="How softly it joins: the width of the smooth fillet where it meets the clay"),
    dataclasses.replace(CH("symmetry", SYMMETRY, "Mirror", "Step", "x"), labels=_MIRROR),
    # a stroke
    CH("brush", BRUSHES, "Brush", "Stroke", "add", when=STROKE),
    N("size", "Size", "Stroke", 0.0005, 10, 0.001, "m", when=STROKE, default=0.03, help="The brush's radius"),
    dataclasses.replace(N("strength", "Strength", "Stroke", 0, 1, 0.01, "", when=STROKE, default=0.5), display="percent"),
    T("accumulate", "Build up", "Stroke", False, S, STROKE),
    X("dabs", "Dabs", "Step data", "", D, STROKE,
      help='The dabs exactly as applied: a file in the project, "clay/<hash>.dabs" (clay_dabs.py)'),
    Param.points("dabList", label="Dabs (inline)", group="Step data", importance=D, valid_when=STROKE, min=9, max=9,
                 default=None, nullable=True, shown="script",
                 help="The dabs written out: [ax, ay, az, nx, ny, nz, bx, by, bz] each (surface point, its normal, the "
                      "pull or crease direction). Saved into a dabs file when the project has a folder"),
    Param.points("path", label="Path", group="Step data", importance=D, valid_when=STROKE, min=3, max=3,
                 default=None, nullable=True, shown="script",
                 help="An agent's stroke: points [x, y, z]; each dab lands where a ray along `dir` from the point "
                      "meets the clay"),
    _V3("dir", "Direction", STROKE, "The way the path's rays point (towards the clay), e.g. [0, 0, -1]"),
]

STILL = {p.name for p in CLAY if p.group in ("Brush", "Clay")}     # settings, never animated


def check_step(clay: dict, step: dict, problems: list):
    """A piece has its centre; a stroke has exactly one path: a dabs file, inline dabs, or path + dir."""
    where = f'{clay["id"]} step {step["id"]}'
    if step.get("step") == "piece":
        if not step.get("at"):
            problems.append(f"{where}: a piece needs `at` (its centre)")
        if step.get("shape") == "capsule" and not step.get("to"):
            problems.append(f"{where}: a capsule needs `to` (its other end)")
        return
    given = [k for k in ("dabs", "dabList", "path") if step.get(k)]
    if len(given) != 1:
        problems.append(f"{where}: a stroke needs exactly one of dabs (a file), dabList (inline) or path + dir; "
                        f"it has {', '.join(given) or 'none'}")
    elif given == ["path"] and not step.get("dir"):
        problems.append(f"{where}: a path stroke needs `dir` (the way its rays point)")
