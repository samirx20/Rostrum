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
from rostrum_core.keys import KEY_FIELDS

from .outline_fields import FIELDS as OUTLINE_FIELDS, OUTLINE_SHAPES
from .rig_fields import RIG

IS = lambda name, value: {"is": [name, value]}  # noqa: E731
ANY = lambda name, *values: {"any": [IS(name, v) for v in values]}  # noqa: E731
NOT = lambda name, value: {"not": IS(name, value)}  # noqa: E731
P, S, D = "primary", "secondary", "deep"


def N(name, label, group, lo, hi, step, unit="", imp=P, when=None, integer=False, default=0.0, help=""):
    return Param.number(name, label=label, group=group, min=lo, max=hi, step=step, unit=unit, importance=imp,
                        valid_when=when, integer=integer, default=default, help=help)


def C(name, label, group, default, imp=P, when=None, help=""):
    return Param.color(name, label=label, group=group, importance=imp, valid_when=when, default=default, help=help)


def CH(name, options, label, group, default, imp=P, when=None, help=""):
    return Param.choice(name, options, label=label, group=group, importance=imp, valid_when=when, default=default,
                        help=help)


def T(name, label, group, default, imp=P, when=None, help=""):
    return Param.toggle(name, label=label, group=group, importance=imp, valid_when=when, default=default, help=help)


def X(name, label, group, default="", imp=P, when=None, help="", refers=None):
    """A text field. `refers`: the item type its text is the id of ("material", "camera"); screens offer those items."""
    return Param.text(name, label=label, group=group, importance=imp, valid_when=when, default=default, help=help, kind=refers)


NO_AIM = IS("aim", "none")
TRANSFORM = [
    N("x", "X", "Position", -1e5, 1e5, 0.001, "m"),
    N("y", "Y", "Position", -1e5, 1e5, 0.001, "m", help="Up"),
    N("z", "Z", "Position", -1e5, 1e5, 0.001, "m", help="Towards the default camera"),
    N("rx", "Turn X", "Rotation", -36000, 36000, 0.1, "°", S, NO_AIM, help="Applied first (tilt)"),
    N("ry", "Turn Y", "Rotation", -36000, 36000, 0.1, "°", S, NO_AIM, help="Applied second (spin around up)"),
    N("rz", "Turn Z", "Rotation", -36000, 36000, 0.1, "°", S, NO_AIM, help="Applied last"),
    N("sx", "Scale X", "Scale", 0, 1000, 0.01, "×", D, default=1.0),
    N("sy", "Scale Y", "Scale", 0, 1000, 0.01, "×", D, default=1.0),
    N("sz", "Scale Z", "Scale", 0, 1000, 0.01, "×", D, default=1.0),
    T("visible", "Visible", "Display", True, S),
    CH("aim", ["none", "point", "item"], "Aim at", "Aim", "none", S,
       help="Point the item's −Z (where cameras and rect/disk lights face) at a point or another item; "
            "its rotation is then worked out every frame"),
    N("aimX", "Aim X", "Aim", -1e5, 1e5, 0.001, "m", S, IS("aim", "point")),
    N("aimY", "Aim Y", "Aim", -1e5, 1e5, 0.001, "m", S, IS("aim", "point")),
    N("aimZ", "Aim Z", "Aim", -1e5, 1e5, 0.001, "m", S, IS("aim", "point")),
    X("aimItem", "Aim at item", "Aim", "", S, IS("aim", "item"), help="The id of the item to look at (its origin)"),
    N("roll", "Roll", "Aim", -36000, 36000, 0.1, "°", S, NOT("aim", "none"),
      help="Turns an aimed item around the way it points: 90 stands a strip light on end, tilts a camera's horizon"),
]

SHAPES = ["box", "sphere", "cylinder", "plane", "disc", "torus", *OUTLINE_SHAPES]
from .light_fields import KINDS as LIGHT_KINDS, LIGHT, STILL as LIGHT_STILL  # noqa: E402  (needs the helpers above)
from .material_fields import MATERIAL  # noqa: E402  (needs the helpers above)
DOF = IS("dof", True)
from .render_fields import RENDER  # noqa: E402  (needs the helpers above)

FIELDS: dict[str, list[Param]] = {
    "group": list(TRANSFORM),
    "mesh": [
        CH("shape", SHAPES, "Shape", "Shape", "box"),
        N("width", "Width", "Shape", 0, 1e4, 0.001, "m", when=ANY("shape", "box", "plane"), default=1.0,
          help="Along X. A plane lies flat, facing up: width (X) × depth (Z)"),
        N("height", "Height", "Shape", 0, 1e4, 0.001, "m", when=ANY("shape", "box", "cylinder"), default=1.0),
        N("depth", "Depth", "Shape", 0, 1e4, 0.001, "m", when=ANY("shape", "box", "plane", *OUTLINE_SHAPES), default=1.0,
          help="Box: along Z. Plane: its other side, along Z (a plane has no height). Text, svg, path2d: how far "
               "the flat outline is pushed out (try 0.02)"),
        N("radius", "Radius", "Shape", 0, 1e4, 0.001, "m", when=ANY("shape", "sphere", "cylinder", "disc", "torus"),
          default=0.5, help="Torus: from its centre to the middle of the ring"),
        N("tube", "Tube radius", "Shape", 0, 1e4, 0.001, "m", when=IS("shape", "torus"), default=0.15),
        *OUTLINE_FIELDS,
        N("bevel", "Bevel", "Shape", 0, 1e3, 0.0005, "m", S, ANY("shape", "box", "cylinder", *OUTLINE_SHAPES),
          help="Rounded edges this wide; real products almost never have razor edges"),
        N("segments", "Segments", "Shape", 1, 256, 1, "", D, NOT("shape", "plane"), integer=True, default=24,
          help="Box: steps around each bevel. Round shapes: steps around"),
        T("smooth", "Smooth shading", "Shape", True, S, help="Smooth normals; off = flat facets"),
        X("material", "Material", "Material", "", help='A material id, or "" for none', refers="material"),
    ] + TRANSFORM,
    "import": [
        X("file", "File", "File", "", help="Absolute path of a .usd / .usda / .usdc / .usdz; the file is never rewritten"),
        X("prim", "Prim", "File", "", D, help='Path inside the file; "" = its default prim'),
        X("material", "Material", "Material", "", S, help='One material over the whole import, or "" to keep the file\'s', refers="material"),
    ] + TRANSFORM,
    # A part of an import: an override on a prim inside the file (path relative to the import's prim).
    "part": [
        X("path", "Path", "Part", "", D, help="Prim path relative to the import's prim, e.g. Body/Screen"),
        X("material", "Material", "Part", "", help='A material id, or "" to keep the file\'s', refers="material"),
        T("visible", "Visible", "Part", True),
    ],
    "light": LIGHT,                     # light_fields.py
    "camera": [
        N("focalLength", "Focal length", "Lens", 1, 2000, 0.1, "mm", default=50.0,
          help="Longer = narrower view and flatter perspective (product shots often 85–150)"),
        N("sensorWidth", "Sensor width", "Lens", 1, 100, 0.1, "mm", D, default=36.0),
        T("dof", "Depth of field", "Focus", False),
        N("fStop", "f-stop", "Focus", 0.5, 64, 0.1, "", when=DOF, default=2.8, help="Smaller = blurrier background"),
        N("focusDistance", "Focus distance", "Focus", 0.001, 1e5, 0.001, "m", when=DOF, default=5.0),
        N("near", "Near clip", "Clipping", 0.0001, 1e4, 0.001, "m", D, default=0.01),
        N("far", "Far clip", "Clipping", 0.01, 1e7, 1, "m", D, default=1000.0),
    ] + TRANSFORM,
    "material": MATERIAL,               # material_fields.py
    # A shot: a camera, a frame size and a stretch of time. Times are seconds; frames = round(seconds × fps),
    # from round(start × fps) to round(end × fps) − 1 (end is where the shot is over).
    "shot": [
        X("camera", "Camera", "Shot", "", help="The id of the camera this shot looks through", refers="camera"),
        N("fps", "Frame rate", "Shot", 1, 120, 1, "fps", integer=True, default=24),
        N("start", "Starts at", "Shot", 0, 36000, 0.001, "s"),
        N("end", "Ends at", "Shot", 0.001, 36000, 0.001, "s", default=2.0),
        N("width", "Width", "Frame", 16, 16384, 1, "px", S, integer=True, default=1920),
        N("height", "Height", "Frame", 16, 16384, 1, "px", S, integer=True, default=1080),
        C("background", "Background", "Frame", "#000000", S, help="What shows where nothing is (not a light)"),

        *RENDER,
    ],
    # A camera rig (rigs.py): holds the camera; its own transform is the base, without aim or scale.
    "rig": RIG + [dataclasses.replace(p, valid_when=None) for p in TRANSFORM
                  if p.name in ("x", "y", "z", "rx", "ry", "rz", "visible")],
    "key": KEY_FIELDS,                   # the one key shape (t in seconds, v or c, ease), shared with 2D
}

ITEMS = ("group", "mesh", "import", "light", "camera", "rig")      # scene items (USD prims)
HOLDERS = ("group", "import", "rig")
LISTS = {"doc": ["items", "materials", "shots"], "group": ["children", "keys"],     # where child items live
         "import": ["children", "parts", "keys"], "mesh": ["keys"], "light": ["keys"], "camera": ["keys"],
         "rig": ["children", "keys"]}
STILL = {"mesh": {p.name for p in FIELDS["mesh"] if p.group == "Shape"},     # a mesh's shape is built once
         "light": LIGHT_STILL,
         "*": {"aim"}}
LABELS = {"group": "Group", "mesh": "Mesh", "import": "Import", "part": "Part", "light": "Light", "camera": "Camera", "rig": "Camera rig",
          "material": "Material", "shot": "Shot", "key": "Key"}


def param(kind: str, name: str) -> Param | None:
    return next((p for p in FIELDS.get(kind, ()) if p.name == name), None)


def defaults(kind: str) -> dict:
    return {p.name: p.default for p in FIELDS[kind]}


def animatable(kind: str) -> list[str]:
    if kind not in ITEMS:
        return []
    still = STILL.get(kind, set()) | STILL["*"]
    return [p.name for p in FIELDS[kind] if p.type in ("number", "color") and p.name not in still]


def unconditional(kind: str) -> list[Param]:
    """The fields as arguments of an add operation: no valid_when (checked on the whole new item, `not_valid`)."""
    return [dataclasses.replace(p, valid_when=None) for p in FIELDS[kind]]


def not_valid(kind: str, item: dict, given) -> list[str]:
    """The given field names that don't apply to `item` as it is (e.g. width on a sphere)."""
    return [n for n in given if (p := param(kind, n)) and not holds(p.valid_when, item)]
