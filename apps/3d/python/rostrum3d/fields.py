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
from rostrum2d import fields as _f2d

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


def X(name, label, group, default="", imp=P, when=None, help=""):
    return Param.text(name, label=label, group=group, importance=imp, valid_when=when, default=default, help=help)


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
]

SHAPES = ["box", "sphere", "cylinder", "plane", "disc", "torus"]
LIGHT_KINDS = ["rect", "disk", "sphere", "distant", "dome"]
DOF = IS("dof", True)

FIELDS: dict[str, list[Param]] = {
    "group": list(TRANSFORM),
    "mesh": [
        CH("shape", SHAPES, "Shape", "Shape", "box"),
        N("width", "Width", "Shape", 0, 1e4, 0.001, "m", when=ANY("shape", "box", "plane"), default=1.0),
        N("height", "Height", "Shape", 0, 1e4, 0.001, "m", when=ANY("shape", "box", "cylinder"), default=1.0),
        N("depth", "Depth", "Shape", 0, 1e4, 0.001, "m", when=ANY("shape", "box", "plane"), default=1.0),
        N("radius", "Radius", "Shape", 0, 1e4, 0.001, "m", when=ANY("shape", "sphere", "cylinder", "disc", "torus"),
          default=0.5, help="Torus: from its centre to the middle of the ring"),
        N("tube", "Tube radius", "Shape", 0, 1e4, 0.001, "m", when=IS("shape", "torus"), default=0.15),
        N("bevel", "Bevel", "Shape", 0, 1e3, 0.0005, "m", S, ANY("shape", "box", "cylinder"),
          help="Rounded edges this wide; real products almost never have razor edges"),
        N("segments", "Segments", "Shape", 1, 256, 1, "", D, NOT("shape", "plane"), integer=True, default=24,
          help="Box: steps around each bevel. Round shapes: steps around"),
        T("smooth", "Smooth shading", "Shape", True, S, help="Smooth normals; off = flat facets"),
        X("material", "Material", "Material", "", help='A material id, or "" for none'),
    ] + TRANSFORM,
    "import": [
        X("file", "File", "File", "", help="Absolute path of a .usd / .usda / .usdc / .usdz; the file is never rewritten"),
        X("prim", "Prim", "File", "", D, help='Path inside the file; "" = its default prim'),
        X("material", "Material", "Material", "", S, help='One material over the whole import, or "" to keep the file\'s'),
    ] + TRANSFORM,
    # A part of an import: an override on a prim inside the file (path relative to the import's prim).
    "part": [
        X("path", "Path", "Part", "", D, help="Prim path relative to the import's prim, e.g. Body/Screen"),
        X("material", "Material", "Part", "", help='A material id, or "" to keep the file\'s'),
        T("visible", "Visible", "Part", True),
    ],
    "light": [
        CH("kind", LIGHT_KINDS, "Kind", "Light", "rect",
           help="rect / disk: soft panels shining along their −Z; sphere: a bulb; distant: the sun; dome: the sky "
                "or an HDR around everything"),
        N("width", "Width", "Shape", 0, 1e3, 0.01, "m", when=IS("kind", "rect"), default=1.0),
        N("height", "Height", "Shape", 0, 1e3, 0.01, "m", when=IS("kind", "rect"), default=1.0),
        N("radius", "Radius", "Shape", 0, 1e3, 0.001, "m", when=ANY("kind", "disk", "sphere"), default=0.5),
        N("angle", "Angle", "Shape", 0, 180, 0.01, "°", when=IS("kind", "distant"), default=0.53,
          help="How wide the sun looks; bigger = softer shadows (the real sun is 0.53°)"),
        X("texture", "HDR image", "Shape", "", when=IS("kind", "dome"), help='Absolute .hdr / .exr path, or "" for a flat colour'),
        C("color", "Colour", "Light", "#ffffff"),
        N("intensity", "Intensity", "Light", 0, 1e6, 0.01, default=1.0),
        N("exposure", "Exposure", "Light", -20, 20, 0.1, "stops", S, help="Each +1 doubles the light"),
        N("temperature", "Temperature", "Light", 0, 20000, 10, "K", S,
          help="Colour of the light in kelvin (2700 warm bulb, 5600 daylight, 7500 shade); 0 = off, use Colour only"),
        T("normalize", "Same brightness at any size", "Light", False, D,
          help="On: resizing the light changes its softness, not its brightness"),
        T("shadows", "Casts shadows", "Light", True, D),
    ] + TRANSFORM,
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
    "material": [
        C("baseColor", "Base colour", "Surface", "#cccccc", when=IS("baseColorTexture", "")),
        X("baseColorTexture", "Base colour image", "Surface", "", S, help='Absolute path of an sRGB image on the UVs; replaces the base colour'),
        N("metallic", "Metallic", "Surface", 0, 1, 0.01, help="1 = metal (its colour tints the reflections)"),
        N("roughness", "Roughness", "Surface", 0, 1, 0.01, default=0.5, when=IS("roughnessTexture", ""),
          help="0 = mirror, 1 = chalk"),
        X("roughnessTexture", "Roughness image", "Surface", "", D, help="A grey image read as raw numbers"),
        N("transmission", "Transmission", "Glass", 0, 1, 0.01, "", S, help="1 = light passes through (glass, water)"),
        N("ior", "Index of refraction", "Glass", 1, 3, 0.01, "", S, default=1.5,
          help="How much light bends: water 1.33, glass 1.5, sapphire 1.77, diamond 2.42"),
        N("coat", "Clear coat", "Coat", 0, 1, 0.01, "", S, help="A thin varnish layer over the surface"),
        N("coatRoughness", "Coat roughness", "Coat", 0, 1, 0.01, "", S, NOT("coat", 0), default=0.03),
        N("anisotropy", "Anisotropy", "Brushed", 0, 1, 0.01, "", D, help="Stretches highlights along one direction (brushed metal)"),
        N("anisotropyRotation", "Brush direction", "Brushed", 0, 1, 0.01, "", D, NOT("anisotropy", 0),
          help="Turns the brushing: 0..1 = 0..360°"),
        X("bumpTexture", "Bump image", "Relief", "", D, help="A grey height image: white is raised"),
        N("bumpStrength", "Bump strength", "Relief", 0, 1, 0.01, "", D, NOT("bumpTexture", ""), default=0.5),
        C("emissionColor", "Glow colour", "Glow", "#ffffff", D, NOT("emissionStrength", 0)),
        N("emissionStrength", "Glow strength", "Glow", 0, 1e4, 0.1, "", D, help="The surface gives off light (screens, LEDs)"),
        N("thinFilm", "Thin film", "Coat", 0, 2000, 1, "nm", D, help="Rainbow coating thickness (anodizing, soap); 0 = off"),
    ],
    # A shot: a camera, a frame size and a stretch of time. Times are seconds; frames = round(seconds × fps),
    # from round(start × fps) to round(end × fps) − 1 (end is where the shot is over).
    "shot": [
        X("camera", "Camera", "Shot", "", help="The id of the camera this shot looks through"),
        N("fps", "Frame rate", "Shot", 1, 120, 1, "fps", integer=True, default=24),
        N("start", "Starts at", "Shot", 0, 36000, 0.001, "s"),
        N("end", "Ends at", "Shot", 0.001, 36000, 0.001, "s", default=2.0),
        N("width", "Width", "Frame", 16, 16384, 1, "px", S, integer=True, default=1920),
        N("height", "Height", "Frame", 16, 16384, 1, "px", S, integer=True, default=1080),
        C("background", "Background", "Frame", "#000000", S, help="What shows where nothing is (not a light)"),
    ],
    "key": _f2d.FIELDS["key"],            # the one key shape (t in seconds, v or c, ease) and easing, shared with 2D
}

ITEMS = ("group", "mesh", "import", "light", "camera")      # scene items (USD prims)
HOLDERS = ("group", "import")
LISTS = {"doc": ["items", "materials", "shots"], "group": ["children", "keys"],     # where child items live
         "import": ["children", "parts", "keys"], "mesh": ["keys"], "light": ["keys"], "camera": ["keys"]}
STILL = {"mesh": {p.name for p in FIELDS["mesh"] if p.group == "Shape"},     # a mesh's shape is built once
         "*": {"aim"}}
LABELS = {"group": "Group", "mesh": "Mesh", "import": "Import", "part": "Part", "light": "Light", "camera": "Camera",
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
