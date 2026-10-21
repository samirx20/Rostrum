"""Every 2D item type's fields: the one table. The field operations, the inspector, the script layer's checks,
the scene description and its defaults all read it. Each field carries `valid_when` and `importance` (rule of
individuality: a control that doesn't apply right now is absent, never greyed).

Animatable = every number and colour field, except those in STILL (they describe the item, not a moment).
"""
from __future__ import annotations

from rostrum_core import Param

from .easing import NAMES as _EASES

IS = lambda name, value: {"is": [name, value]}  # noqa: E731
P = "primary"
S = "secondary"
D = "deep"


def N(name, label, group, lo, hi, step, unit="", imp=P, when=None, integer=False, default=0.0, help=""):
    return Param.number(name, label=label, group=group, min=lo, max=hi, step=step, unit=unit, importance=imp,
                        valid_when=when, integer=integer, default=default, help=help)


def C(name, label, group, default, imp=P, when=None):
    return Param.color(name, label=label, group=group, importance=imp, valid_when=when, default=default)


def CH(name, options, label, group, default, imp=P, when=None):
    return Param.choice(name, options, label=label, group=group, importance=imp, valid_when=when, default=default)


def T(name, label, group, default, imp=P, when=None, help=""):
    return Param.toggle(name, label=label, group=group, importance=imp, valid_when=when, default=default, help=help)


def X(name, label, group, default, imp=P, help=""):
    return Param.text(name, label=label, group=group, importance=imp, default=default, help=help)


BLENDS = ["normal", "screen", "add", "multiply", "overlay", "soft-light"]

# Every layer has these (position is where its anchor sits in the composition, in px).
TRANSFORM = [
    N("x", "X", "Transform", -20000, 20000, 1, "px", default=960.0),
    N("y", "Y", "Transform", -20000, 20000, 1, "px", default=540.0),
    N("scale", "Scale", "Transform", 0, 100, 0.01, "×", default=1.0),
    N("rotation", "Rotation", "Transform", -36000, 36000, 0.1, "°"),
    N("opacity", "Opacity", "Transform", 0, 1, 0.01, default=1.0),
    N("anchorX", "Anchor X", "Transform", -10, 10, 0.01, "", S, default=0.5, help="0 = left edge, 1 = right edge"),
    N("anchorY", "Anchor Y", "Transform", -10, 10, 0.01, "", S, default=0.5, help="0 = top edge, 1 = bottom edge"),
    N("scaleX", "Stretch X", "Transform", 0, 100, 0.01, "×", D, default=1.0),
    N("scaleY", "Stretch Y", "Transform", 0, 100, 0.01, "×", D, default=1.0),
    N("tiltX", "Tilt X", "Depth", -180, 180, 0.1, "°", D, help="Turn around the horizontal axis (2.5D)"),
    N("tiltY", "Tilt Y", "Depth", -180, 180, 0.1, "°", D, help="Turn around the vertical axis (2.5D)"),
    N("start", "Starts at", "Timing", 0, 36000, 0.01, "s", S, help="The layer appears at this time"),
    N("end", "Ends at", "Timing", 0, 36000, 0.01, "s", S, default=36000.0, help="The layer is gone from this time"),
    CH("blend", BLENDS, "Blend", "Look", "normal", D),
]

STROKE = IS("stroke", True)

FIELDS: dict[str, list[Param]] = {
    "comp": [
        N("width", "Width", "Frame", 16, 8192, 1, "px", integer=True, default=1920),
        N("height", "Height", "Frame", 16, 8192, 1, "px", integer=True, default=1080),
        N("fps", "Frame rate", "Frame", 1, 120, 1, "fps", integer=True, default=30),
        N("duration", "Length", "Frame", 0.04, 3600, 0.01, "s", default=5.0),
        C("background", "Background", "Look", "#000000"),
    ],
    "shape": [
        CH("shape", ["rect", "ellipse"], "Shape", "Shape", "rect"),
        N("w", "Width", "Shape", 0, 20000, 1, "px", default=200.0),
        N("h", "Height", "Shape", 0, 20000, 1, "px", default=200.0),
        N("radius", "Corner radius", "Shape", 0, 10000, 1, "px", when=IS("shape", "rect")),
        C("fill", "Fill", "Fill", "#ffffff"),
        T("stroke", "Outline", "Outline", False, S),
        C("strokeColor", "Outline colour", "Outline", "#ffffff", S, STROKE),
        N("strokeWidth", "Outline width", "Outline", 0, 500, 0.5, "px", S, STROKE, default=2.0),
    ] + TRANSFORM,
    "text": [
        X("body", "Text", "Text", "Text"),
        N("size", "Size", "Text", 1, 2000, 1, "px", default=96.0),
        N("weight", "Weight", "Text", 1, 1000, 1, "", default=600.0),
        C("color", "Colour", "Text", "#ffffff"),
        CH("align", ["left", "center", "right"], "Align", "Text", "center", S),
        N("tracking", "Letter spacing", "Text", -0.5, 2, 0.001, "em", S, help="Space between letters"),
        N("lineHeight", "Line height", "Text", 0.5, 4, 0.01, "×", S, default=1.1),
        X("font", "Font", "Font", "Roboto Flex", S),
        N("stretch", "Width", "Font", 25, 200, 1, "%", D, default=100.0, help="Variable font width"),
        N("boxWidth", "Box width", "Text", 0, 20000, 1, "px", D, help="0 = one line, as wide as the text"),
        T("stroke", "Outline", "Outline", False, D),
        C("strokeColor", "Outline colour", "Outline", "#ffffff", D, STROKE),
        N("strokeWidth", "Outline width", "Outline", 0, 100, 0.5, "px", D, STROKE, default=1.0),
    ] + TRANSFORM,
    "image": [
        X("src", "File", "Image", "", help="Absolute path, or relative to the project folder"),
        N("w", "Width", "Image", 0, 20000, 1, "px", default=640.0),
        N("h", "Height", "Image", 0, 20000, 1, "px", default=360.0),
        CH("fit", ["cover", "contain", "stretch"], "Fit", "Image", "cover", S),
        N("radius", "Corner radius", "Image", 0, 10000, 1, "px", S),
    ] + TRANSFORM,
    "group": [
        N("w", "Width", "Group", 0, 20000, 1, "px", default=1920.0),
        N("h", "Height", "Group", 0, 20000, 1, "px", default=1080.0),
        T("clip", "Clip to box", "Group", False, S, help="Hide children outside the group's box"),
    ] + TRANSFORM,
    # A drawing: painted strokes (the shared painting kit), one drawing per frame or held for several. Its canvas
    # is w × h px; untransformed it covers that box with the canvas's px = the composition's px.
    "drawing": [
        N("w", "Canvas width", "Drawing", 16, 8192, 1, "px", S, integer=True, default=1920),
        N("h", "Canvas height", "Drawing", 16, 8192, 1, "px", S, integer=True, default=1080),
    ] + TRANSFORM,
    # One drawing of a drawing layer: shown from frame `at` until the next drawing (held), none before the first.
    # It is a painting-kit canvas: it holds paint layers (`paints`) and paint masks.
    "frame": [
        N("at", "Frame", "Drawing", 0, 10**7, 1, "f", integer=True, help="The frame number this drawing appears at"),
    ],
    # Effects: a layer's look, in order (a gradient fills the shape, or the letters of a text).
    "blur": [N("radius", "Blur", "Blur", 0, 1000, 0.5, "px", default=12.0)],
    "glow": [
        N("radius", "Size", "Glow", 0, 1000, 0.5, "px", default=40.0),
        N("strength", "Strength", "Glow", 0, 4, 0.01, default=0.8),
        T("ownColor", "Layer's own colour", "Glow", True),
        C("color", "Colour", "Glow", "#ffffff", when=IS("ownColor", False)),
    ],
    "gradient": [
        CH("style", ["linear", "radial"], "Style", "Gradient", "linear"),
        N("angle", "Angle", "Gradient", -360, 360, 1, "°", when=IS("style", "linear"), default=180.0),
        C("color1", "From", "Gradient", "#ffffff"),
        C("color2", "To", "Gradient", "#808080"),
        T("middle", "Middle colour", "Gradient", False, S),
        C("color3", "Middle", "Gradient", "#c0c0c0", S, IS("middle", True)),
        N("mid", "Middle at", "Gradient", 0, 1, 0.01, "", S, IS("middle", True), default=0.5),
    ],
    "shadow": [
        N("dx", "Offset X", "Shadow", -2000, 2000, 1, "px"),
        N("dy", "Offset Y", "Shadow", -2000, 2000, 1, "px", default=20.0),
        N("radius", "Softness", "Shadow", 0, 1000, 0.5, "px", default=40.0),
        C("color", "Colour", "Shadow", "#000000"),
        N("strength", "Strength", "Shadow", 0, 1, 0.01, default=0.5),
    ],
    # A mask: the part of the layer that shows (in the layer's own px, from its top-left corner).
    "mask": [
        CH("shape", ["rect", "ellipse"], "Shape", "Mask", "rect"),
        N("x", "X", "Mask", -20000, 20000, 1, "px"),
        N("y", "Y", "Mask", -20000, 20000, 1, "px"),
        N("w", "Width", "Mask", 0, 20000, 1, "px", default=200.0),
        N("h", "Height", "Mask", 0, 20000, 1, "px", default=200.0),
        N("radius", "Corner radius", "Mask", 0, 10000, 1, "px", S, IS("shape", "rect")),
        N("feather", "Feather", "Mask", 0, 1000, 0.5, "px", S),
        T("invert", "Invert", "Mask", False, S),
    ],
    # A key: the value one field has at one time. Its `ease` shapes the stretch to the next key.
    # A key holds `v` (a number field) or `c` (a colour field); its `prop` names the field and never changes.
    "key": [
        N("t", "Time", "Key", 0, 36000, 0.001, "s"),
        N("v", "Value", "Key", -1e9, 1e9, 0.01, when={"fact": "number"}),
        C("c", "Value", "Key", "#ffffff", when={"fact": "color"}),
        CH("ease", list(_EASES), "Ease", "Key", "smooth"),
        N("x1", "Curve x1", "Curve", 0, 1, 0.01, when=IS("ease", "custom"), default=0.25),
        N("y1", "Curve y1", "Curve", -2, 3, 0.01, when=IS("ease", "custom"), default=0.1),
        N("x2", "Curve x2", "Curve", 0, 1, 0.01, when=IS("ease", "custom"), default=0.25),
        N("y2", "Curve y2", "Curve", -2, 3, 0.01, when=IS("ease", "custom"), default=1.0),
        N("stiffness", "Stiffness", "Spring", 1, 2000, 1, when=IS("ease", "spring"), default=170.0),
        N("damping", "Damping", "Spring", 0, 200, 0.1, when=IS("ease", "spring"), default=12.0),
    ],
}

LAYERS = ("shape", "text", "image", "group", "drawing")
EFFECTS = ("blur", "glow", "gradient", "shadow")
ANIMATED_OWNERS = LAYERS + EFFECTS + ("mask",)
STILL = {"comp": {"width", "height", "fps", "duration", "background"}, "drawing": {"w", "h"},
         "*": {"start", "end", "boxWidth"}}
LABELS = {"comp": "Composition", "shape": "Shape", "text": "Text", "image": "Image", "group": "Group", "drawing": "Drawing", "frame": "Drawing frame",
          "blur": "Blur", "glow": "Glow", "gradient": "Gradient", "shadow": "Shadow", "mask": "Mask", "key": "Key"}


def param(kind: str, name: str) -> Param | None:
    return next((p for p in FIELDS.get(kind, ()) if p.name == name), None)


def defaults(kind: str) -> dict:
    return {p.name: p.default for p in FIELDS[kind]}


def animatable(kind: str) -> list[str]:
    """The fields of `kind` that keys may drive."""
    still = STILL.get(kind, set()) | STILL["*"]
    return [p.name for p in FIELDS.get(kind, ()) if p.type in ("number", "color") and p.name not in still]
