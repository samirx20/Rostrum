"""A clay's fields and its steps' fields (item_fields.py takes them in). A clay is a lump you sculpt: its shape is
its `steps`, applied in order by the core (pieces: spheres, capsules, drawn outlines puffed up, spun profiles and
other items turned into clay, joined or carved; strokes: brush dabs). A hidden step is left out of the shape.
Its Brush group holds the *next* stroke's settings, so screens show them from field data; each stroke step keeps its
own copy. All positions are in the clay's own space, in metres. Dab files: clay_dabs.py; the scene: clay_scene.py.
"""
from __future__ import annotations

import dataclasses

from rostrum_core import Param

from .field_kit import ANY, CH, D, IS, N, S, SCULPTING, T, TRANSFORM, X
from .paint_fields import SIZE as PAINT_SIZE

BRUSHES = ["add", "carve", "smooth", "pull", "flatten", "crease", "mask"]
SYMMETRY = ["off", "x"]
_MIRROR = {"off": "Off", "x": "Left–right"}
DETAIL_MODES = ["auto", "fixed"]
SHAPES = ["sphere", "capsule", "outline", "spin", "item"]
PIECE, STROKE = IS("step", "piece"), IS("step", "stroke")
BALL = {"all": [PIECE, ANY("shape", "sphere", "capsule")]}
OUTLINE, SPIN, FROM = ({"all": [PIECE, IS("shape", s)]} for s in ("outline", "spin", "item"))
DRAWN = {"all": [PIECE, ANY("shape", "outline", "spin")]}
SOURCES = ("mesh", "combine", "import", "part")      # what Turn into clay takes: exact parts and imports
FIXED = IS("detailMode", "fixed")
_INVERT = ("Ctrl's opposite: Flatten puffs out, Crease pinches to a ridge, Mask takes the mask away (Add and Carve "
           "swap the brush instead)")

BONED = {"fact": "boned"}
# Pose by dragging (ops_pose.py): a clay's `bones` are found from its shape (pose.find_joints) and posed by keys on
# their Turn, as a mesh's chain is (skin.py).
POSE = [
    T("skinned", "Bend with joints", "Pose", True, S, BONED,
      help="Off: the clay keeps its resting shape; its joints and their keys stay"),
    dataclasses.replace(CH("jointNames", ["plain", "humanoid"], "Joint names", "Pose", "plain", S, BONED,
                           help="Plain: body, chest, arm.L, forearm.L, foot.R … Humanoid: Hips, Spine, LeftUpperArm, "
                                "LeftLowerArm, RightFoot … (Unity's Humanoid / VRM), for motion capture and humanoid "
                                "rigs. The bones' ids stay the same either way"),
                        labels={"plain": "Plain", "humanoid": "Humanoid"}),
    Param.points("holds", label="Holds", group="Pose data", importance=D, min=3, max=3, default=None, nullable=True,
                 help="Spots that stay put while you drag (pose.hold): [x, y, z] each, on the RESTING clay in its own "
                      "space; each holds the bone under it (the nearest bone at rest)"),
    Param.text("jointsKey", label="Joints found for", group="Pose data", importance=D, default="", shown="script",
               help="The clay's last step key when its joints were found; another key = the shape changed since "
                    "(pose_joints.out_of_date)"),
]

CLAY = [
    CH("brush", BRUSHES, "Brush", "Brush", "add", when=SCULPTING,
       help="Add builds clay up, Carve digs in, Smooth evens bumps out; Pull drags the surface along the stroke, "
            "Flatten presses it to a plane, Crease cuts a sharp fold; Mask paints a mask that protects the clay "
            "from every other brush"),
    N("brushSize", "Size", "Brush", 0.0005, 10, 0.001, "m", when=SCULPTING, default=0.03, help="The brush's radius"),
    dataclasses.replace(N("brushStrength", "Strength", "Brush", 0, 1, 0.01, "", when=SCULPTING, default=0.5),
                        display="percent"),
    dataclasses.replace(CH("symmetry", SYMMETRY, "Mirror", "Brush", "x", when=SCULPTING,
                           help="Left–right: every stroke and piece is mirrored across the clay's own X = 0"),
                        labels=_MIRROR),
    T("accumulate", "Build up", "Brush", False, S, SCULPTING,
      help="On: going over the same place keeps adding. Off: one stroke adds at most its strength, however often "
           "it passes"),
    N("brushFalloff", "Falloff", "Brush", 0, 1, 0.01, "", S, SCULPTING, default=0.5,
      help="How the brush fades to its edge: 0 = soft, 1 = a hard edge"),
    dataclasses.replace(N("brushSpacing", "Spacing", "Brush", 0.05, 1, 0.01, "", S, SCULPTING, default=0.3,
                          help="How far apart the dabs of a stroke are, as a share of the brush's radius"),
                        display="percent"),
    T("frontOnly", "Front faces only", "Brush", True, S, SCULPTING,
      help="On: a dab never reaches through a thin part to the clay's far side (it skips a surface facing away "
           "from the camera)"),
    dataclasses.replace(CH("detailMode", DETAIL_MODES, "Detail", "Clay", "auto", D,
                           help="Auto: worked out from the shot cameras that see the clay, about one grain per "
                                "1.5 pixels at the closest one (clay_detail.py). Fixed: the Detail size you type"),
                        labels={"auto": "Follows the camera", "fixed": "Fixed"}),
    N("detail", "Detail size", "Clay", 0.0002, 0.05, 0.0001, "m", D, FIXED, default=0.002,
      help="How fine the clay is when Detail is Fixed: the size of its smallest grain. Smaller = finer, slower and "
           "more memory"),
    X("material", "Material", "Material", "", help='A material id, or "" for none', refers="material"),
    PAINT_SIZE,                         # a clay is a paint canvas (paint_fields.py, clay_paint.py)
    *POSE,                              # its joints (ops_pose.py, pose_joints.py)
] + TRANSFORM

_V3 = lambda name, label, when, help: Param.list(name, "number", label=label, group="Step data", importance=D,  # noqa: E731
                                                 valid_when=when, min=-1e5, max=1e5, min_items=3, max_items=3,
                                                 default=None, nullable=True, help=help)

STEP = [
    CH("step", ["piece", "stroke"], "Step", "Step", "piece", D, help="A piece (a shape joined or carved) or a brush stroke"),
    X("name", "Name", "Step", "", S, help='A word for the step ("body", "nose"); optional. The Steps list shows it'),
    T("hidden", "Hidden", "Step", False, D,
      help="Left out of the clay's shape, kept: showing it again brings it back (the Steps list's eye)"),
    # a piece
    dataclasses.replace(CH("shape", SHAPES, "Shape", "Piece", "sphere", D, PIECE,
                           help="sphere / capsule (at, to, radius); outline: a drawn outline puffed up (plane, "
                                "outline, puff); spin: a profile spun round an axis (plane, profile); item: another "
                                "item turned into clay (source)"),
                        labels={"outline": "Drawn", "spin": "Spun", "item": "From an item"}),
    _V3("at", "At", BALL, "Its centre (a capsule: one end), in the clay's own space"),
    _V3("to", "To", {"all": [PIECE, IS("shape", "capsule")]}, "A capsule's other end"),
    N("radius", "Radius", "Piece", 0.0001, 100, 0.001, "m", when=BALL, default=0.1),
    dataclasses.replace(N("puff", "Puff", "Piece", 0.1, 3, 0.01, "", when=OUTLINE, default=1.0,
                          help="How thick a drawn shape is: 1 = round (as thick in the middle as the outline is wide "
                               "there), less is flatter, more is fatter"), display="percent"),
    Param.list("plane", "number", label="Plane", group="Step data", importance=D, valid_when=DRAWN, min=-1e5,
               max=1e5, min_items=9, max_items=9, default=None, nullable=True, shown="script",
               help="[ox, oy, oz, ux, uy, uz, vx, vy, vz]: the plane's origin and two unit, perpendicular axes, in the "
                    "clay's own space. A drawn shape puffs both ways along u × v; a spun one turns round v (through "
                    "the origin), u pointing to the profile's side"),
    Param.points("outline", label="Outline", group="Step data", importance=D, valid_when=OUTLINE, min=2, max=2,
                 default=None, nullable=True, shown="script",
                 help="[[u, v], …] at least 3 points in the plane (metres), closed last → first; may cross itself"),
    Param.points("profile", label="Profile", group="Step data", importance=D, valid_when=SPIN, min=2, max=2,
                 default=None, nullable=True, shown="script",
                 help="[[r, h], …] at least 2 points: r ≥ 0 the distance from the axis, h the height along v; its "
                      "ends are joined to the axis"),
    X("source", "From", "Piece", "", D, FROM, refers="item",
      help="The id of the exact part or import it was made from (hidden by Turn into clay, not deleted)"),
    Param.text("sourceKey", label="Source key", group="Step data", importance=D, valid_when=FROM, default="",
               shown="script", help="A hash of the source's fields when it was made (clay_shapes.source_key); the "
                                    "scene works it out again from the source as it is now"),
    CH("mode", ["add", "carve"], "Mode", "Piece", "add", when=PIECE, help="Add joins it on; Carve cuts it out"),
    N("blend", "Blend", "Piece", 0, 100, 0.001, "m", S, PIECE, default=0.0,
      help="How softly it joins: the width of the smooth fillet where it meets the clay"),
    dataclasses.replace(CH("symmetry", SYMMETRY, "Mirror", "Step", "x"), labels=_MIRROR),
    # a stroke
    CH("brush", BRUSHES, "Brush", "Stroke", "add", when=STROKE),
    N("size", "Size", "Stroke", 0.0005, 10, 0.001, "m", when=STROKE, default=0.03, help="The brush's radius"),
    dataclasses.replace(N("strength", "Strength", "Stroke", 0, 1, 0.01, "", when=STROKE, default=0.5), display="percent"),
    T("accumulate", "Build up", "Stroke", False, S, STROKE),
    N("falloff", "Falloff", "Stroke", 0, 1, 0.01, "", S, STROKE, default=0.5, help="0 = soft edge, 1 = hard edge"),
    dataclasses.replace(N("spacing", "Spacing", "Stroke", 0.05, 1, 0.01, "", S, STROKE, default=0.3,
                          help="Dab spacing, as a share of the radius"), display="percent"),
    T("frontOnly", "Front faces only", "Stroke", True, S, STROKE),
    T("invert", "Opposite", "Stroke", False, S, STROKE, help=_INVERT),
    X("dabs", "Dabs", "Step data", "", D, STROKE,
      help='The dabs exactly as applied: a file in the project, "clay/<hash>.dabs" (clay_dabs.py)'),
    Param.points("dabList", label="Dabs (inline)", group="Step data", importance=D, valid_when=STROKE, min=9, max=11,
                 default=None, nullable=True, shown="script",
                 help="The dabs written out: [ax, ay, az, nx, ny, nz, bx, by, bz] each (surface point, its normal, the "
                      "pull or crease direction), optionally + [radiusScale, strengthScale] (pen pressure; 1 1 "
                      "without). Saved into a dabs file when the project has a folder"),
    Param.points("path", label="Path", group="Step data", importance=D, valid_when=STROKE, min=3, max=3,
                 default=None, nullable=True, shown="script",
                 help="An agent's stroke: points [x, y, z]; each dab lands where a ray along `dir` from the point "
                      "meets the clay"),
    _V3("dir", "Direction", STROKE, "The way the path's rays point (towards the clay), e.g. [0, 0, -1]"),
]

STILL = {p.name for p in CLAY if p.group in ("Brush", "Clay", "Paint")}     # settings, never animated


def _plane(where: str, plane, problems: list):
    if not plane or len(plane) != 9:
        return problems.append(f"{where}: needs `plane` (9 numbers: origin, u, v)")
    u, v = plane[3:6], plane[6:]
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))  # noqa: E731
    if abs(dot(u, u) - 1) > 1e-3 or abs(dot(v, v) - 1) > 1e-3 or abs(dot(u, v)) > 1e-3:
        problems.append(f"{where}: `plane`'s u and v must be unit length and perpendicular")


def check_step(clay: dict, step: dict, problems: list, items: dict | None = None):
    """A piece has what its shape needs (a ball its centre; a drawing its plane and ≥ 3 outline points; a spin its
    plane and ≥ 2 profile points at r ≥ 0; an item a real exact part or import, looked up in `items`, id → item);
    a stroke has exactly one path: a dabs file, inline dabs, or path + dir."""
    where = f'{clay["id"]} step {step["id"]}'
    if step.get("step") == "piece":
        shape = step.get("shape", "sphere")
        if shape in ("sphere", "capsule") and not step.get("at"):
            problems.append(f"{where}: a piece needs `at` (its centre)")
        if shape == "capsule" and not step.get("to"):
            problems.append(f"{where}: a capsule needs `to` (its other end)")
        if shape in ("outline", "spin"):
            _plane(where, step.get("plane"), problems)
        if shape == "outline" and len(step.get("outline") or []) < 3:
            problems.append(f"{where}: a drawn shape needs `outline` with at least 3 points")
        if shape == "spin":
            prof = step.get("profile") or []
            if len(prof) < 2 or any(p[0] < 0 for p in prof):
                problems.append(f"{where}: a spun shape needs `profile` with at least 2 points, each r ≥ 0")
        if shape == "item":
            src = (items or {}).get(step.get("source") or "")
            if not step.get("source") or (items is not None and src is None):
                problems.append(f'{where}: no item "{step.get("source", "")}" to make the clay from (`source`)')
            elif src is not None and src.get("type") not in SOURCES:
                problems.append(f'{where}: `source` "{step["source"]}" is a {src.get("type")}; clay is made from an '
                                "exact part or an import")
        return
    given = [k for k in ("dabs", "dabList", "path") if step.get(k)]
    if len(given) != 1:
        problems.append(f"{where}: a stroke needs exactly one of dabs (a file), dabList (inline) or path + dir; "
                        f"it has {', '.join(given) or 'none'}")
    elif given == ["path"] and not step.get("dir"):
        problems.append(f"{where}: a path stroke needs `dir` (the way its rays point)")
