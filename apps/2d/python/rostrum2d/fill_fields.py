"""A layer's fill as a paint (SPEC 2d-design-v2 § 6): solid, a linear / radial / angular gradient (on a shape, a
path or a text's letters) or a picture (shapes and paths: PICTURE, fields the engine reads itself). The paint is fields on the layer (its type and the gradient's geometry, animatable) plus its
stops: child items `stop` (at, color, opacity), each with its own keys, so a stop's colour and position animate like
any other field. "None" is the layer's `filled` off (a text has no None). fill_paint.py reads and writes it as one
paint; scene.py hands it to the engine (fill_paint.lower). Document-side only: the engine never sees these fields.

Geometry (the renderer's, CSS's): linear `gradAngle` 0° = bottom to top, 90° = left to right, across the box through
its centre; radial = the ellipse touching the box's nearest sides around (gradX, gradY), fractions of the box;
angular = the sweep from `gradAngle` (0° = up, clockwise) around (gradX, gradY). With "From point to point" on
(`gradSpan` "points", shapes and paths): linear from (gradX1, gradY1) to (gradX2, gradY2), radial with radii
(gradRX, gradRY), all fractions of the box: the canvas handles set length as well as direction.
"""
from __future__ import annotations

from rostrum_core import Param

OWNERS = ("shape", "text", "path")
GRADIENTS = ("linear", "radial", "angular")
TYPES = ("solid", *GRADIENTS, "picture")
TEXT_TYPES = ("solid", *GRADIENTS)                          # a text's letters take no picture yet
G = "Fill"
_GRAD = {"any": [{"is": ["fillType", t]} for t in GRADIENTS]}
_ANGLED = {"any": [{"is": ["fillType", "linear"]}, {"is": ["fillType", "angular"]}]}
_CENTRED = {"any": [{"is": ["fillType", "radial"]}, {"is": ["fillType", "angular"]}]}

LAYER = [
    Param.choice("fillType", list(TYPES), label="Fill type", group=G, default="solid", importance="deep",
                 labels={"solid": "Solid", "linear": "Linear", "radial": "Radial", "angular": "Angular", "picture": "Picture"}),
    Param.number("gradAngle", label="Gradient angle", group=G, min=-360, max=360, step=0.1, unit="°", default=90.0,
                 importance="deep", valid_when=_ANGLED, help="Linear: the direction (90° = left to right). Angular: where the sweep starts (0° = up)"),
    Param.number("gradX", label="Gradient centre X", group=G, min=-5, max=6, step=0.01, default=0.5, importance="deep",
                 valid_when=_CENTRED, display="percent", help="Fraction of the layer's box: 0 = left edge, 1 = right edge"),
    Param.number("gradY", label="Gradient centre Y", group=G, min=-5, max=6, step=0.01, default=0.5, importance="deep",
                 valid_when=_CENTRED, display="percent", help="Fraction of the layer's box: 0 = top edge, 1 = bottom edge"),
]
# A solid fill's opacity: a field the engine reads itself (a gradient's is its stops'); old files have none = 1.
OPACITY = [
    Param.number("fillOpacity", label="Fill opacity", group=G, min=0, max=1, step=0.01, default=1.0, importance="deep",
                 valid_when={"is": ["fillType", "solid"]}, display="percent",
                 help="How much of the solid colour shows (the stroke and the layer's own opacity are separate)"),
]
_POINTS = {"all": [{"is": ["gradSpan", "points"]}, {"any": [{"is": ["fillType", "linear"]}, {"is": ["fillType", "radial"]}]}]}
_LIN = {"all": [{"is": ["gradSpan", "points"]}, {"is": ["fillType", "linear"]}]}
_RAD = {"all": [{"is": ["gradSpan", "points"]}, {"is": ["fillType", "radial"]}]}


def _frac(name, label, default, when):
    return Param.number(name, label=label, group=G, min=-5, max=6, step=0.01, default=default, importance="deep",
                        valid_when=when, display="percent")


LAYER += [
    Param.choice("gradSpan", ["box", "points"], label="Gradient span", group=G, default="box", importance="deep",
                 valid_when={"any": [{"is": ["fillType", "linear"]}, {"is": ["fillType", "radial"]}]},
                 labels={"box": "Across the box", "points": "From point to point"}),
    _frac("gradX1", "Gradient start X", 0.0, _LIN), _frac("gradY1", "Gradient start Y", 0.5, _LIN),
    _frac("gradX2", "Gradient end X", 1.0, _LIN), _frac("gradY2", "Gradient end Y", 0.5, _LIN),
    _frac("gradRX", "Gradient radius X", 0.5, _RAD), _frac("gradRY", "Gradient radius Y", 0.5, _RAD),
]
NAMES = {p.name for p in LAYER}           # scene.python_only: lowered by fill_paint, never sent as they are

STOP = [
    Param.number("at", label="Position", group="Stop", min=0, max=1, step=0.001, default=0.0, display="percent"),
    Param.color("color", label="Colour", group="Stop", default="#ffffff"),
    Param.number("opacity", label="Opacity", group="Stop", min=0, max=1, step=0.01, default=1.0, display="percent"),
]

# The gradient effect's free geometry (the engine's stage_fill.rs), lowered from the layer's grad* fields above.
_EFFECT_POINTS = {"is": ["span", "points"]}
GEOMETRY = [
    Param.choice("span", ["box", "points"], label="Span", group="Gradient", default="box", importance="deep",
                 labels={"box": "Across the box", "points": "From point to point"}),
    *(Param.number(n, label=l, group="Gradient", min=-5, max=6, step=0.01, default=d, importance="deep",
                   valid_when=_EFFECT_POINTS, display="percent")
      for n, l, d in (("x1", "Start X", 0.0), ("y1", "Start Y", 0.5), ("x2", "End X", 1.0), ("y2", "End Y", 0.5),
                      ("rx", "Radius X", 0.5), ("ry", "Radius Y", 0.5))),
]

# A picture fill: fields the engine reads on shapes and paths. scene.py sends fillPicture "" unless the fill type is
# picture, so a picture chosen once and then left for a colour is kept but not drawn.
_PIC = {"is": ["fillType", "picture"]}
PICTURE = [
    Param.text("fillPicture", label="Picture", group=G, default="", importance="primary", valid_when=_PIC, control="file",
               help="The picture file that fills the shape, clipped to it"),
    Param.choice("fillFit", ["fill", "fit", "tile", "stretch"], label="Picture fit", group=G, default="fill",
                 importance="primary", valid_when=_PIC,
                 labels={"fill": "Fill", "fit": "Fit", "tile": "Tile", "stretch": "Stretch"}),
    Param.number("fillScale", label="Picture scale", group=G, min=0.01, max=100, step=0.01, default=1.0,
                 importance="secondary", valid_when=_PIC, display="percent"),
]
