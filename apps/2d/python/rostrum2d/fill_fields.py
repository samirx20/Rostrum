"""A layer's fill as a paint (SPEC 2d-design-v2 § 6): solid or a linear / radial / angular gradient, on a shape, a
path or a text's letters. The paint is fields on the layer (its type and the gradient's geometry, animatable) plus its
stops: child items `stop` (at, color, opacity), each with its own keys, so a stop's colour and position animate like
any other field. "None" is the layer's `filled` off (a text has no None). fill_paint.py reads and writes it as one
paint; scene.py hands it to the engine (fill_paint.lower). Document-side only: the engine never sees these fields.

Geometry (the renderer's, CSS's): linear `gradAngle` 0° = bottom to top, 90° = left to right, across the box through
its centre; radial = the ellipse touching the box's nearest sides around (gradX, gradY), fractions of the box;
angular = the sweep from `gradAngle` (0° = up, clockwise) around (gradX, gradY).
"""
from __future__ import annotations

from rostrum_core import Param

OWNERS = ("shape", "text", "path")
GRADIENTS = ("linear", "radial", "angular")
TYPES = ("solid", *GRADIENTS)
G = "Fill"
_GRAD = {"any": [{"is": ["fillType", t]} for t in GRADIENTS]}
_ANGLED = {"any": [{"is": ["fillType", "linear"]}, {"is": ["fillType", "angular"]}]}
_CENTRED = {"any": [{"is": ["fillType", "radial"]}, {"is": ["fillType", "angular"]}]}

LAYER = [
    Param.choice("fillType", list(TYPES), label="Fill type", group=G, default="solid", importance="deep",
                 labels={"solid": "Solid", "linear": "Linear", "radial": "Radial", "angular": "Angular"}),
    Param.number("gradAngle", label="Gradient angle", group=G, min=-360, max=360, step=0.1, unit="°", default=90.0,
                 importance="deep", valid_when=_ANGLED, help="Linear: the direction (90° = left to right). Angular: where the sweep starts (0° = up)"),
    Param.number("gradX", label="Gradient centre X", group=G, min=-5, max=6, step=0.01, default=0.5, importance="deep",
                 valid_when=_CENTRED, display="percent", help="Fraction of the layer's box: 0 = left edge, 1 = right edge"),
    Param.number("gradY", label="Gradient centre Y", group=G, min=-5, max=6, step=0.01, default=0.5, importance="deep",
                 valid_when=_CENTRED, display="percent", help="Fraction of the layer's box: 0 = top edge, 1 = bottom edge"),
]
NAMES = {p.name for p in LAYER}           # scene.python_only: lowered by fill_paint, never sent as they are

STOP = [
    Param.number("at", label="Position", group="Stop", min=0, max=1, step=0.001, default=0.0, display="percent"),
    Param.color("color", label="Colour", group="Stop", default="#ffffff"),
    Param.number("opacity", label="Opacity", group="Stop", min=0, max=1, step=0.01, default=1.0, display="percent"),
]
