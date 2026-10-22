"""The painting kit's item types and their fields: the one table. Brushes are data: every brush setting is a Param
with its range, importance and `valid_when`, so the brush panel, the stroke inspector, the MCP schema and the checks
of `stroke.add` all read the same list (rule of individuality: a setting that doesn't apply right now is absent).

A host app puts a kit **canvas** in its own item type (2D: a drawing's `frame`); a canvas holds `paints` (paint
layers, bottom first) and `paintmasks`. A paint layer holds `strokes`, in painting order.
"""
from __future__ import annotations

from rostrum_core import Param

from .marks import MODES, TIPS

LAYER_MODES = ("normal", "multiply", "screen", "add")
CANVAS_LISTS = ["paints", "paintmasks"]                  # a host's canvas type holds these
LISTS = {"paint": ["strokes"], "stroke": [], "fill": [], "paintmask": []}
HOLDS = {"paints": ("paint",), "strokes": ("stroke", "fill"), "paintmasks": ("paintmask",)}   # a fill is laid in order too
P, S, D = "primary", "secondary", "deep"
IS = lambda name, value: {"is": [name, value]}  # noqa: E731


def N(name, label, lo, hi, step, default, imp=P, unit="", when=None, group="Brush", integer=False, help="", display=""):
    return Param.number(name, label=label, min=lo, max=hi, step=step, default=default, importance=imp, unit=unit,
                        valid_when=when, group=group, integer=integer, help=help, display=display)


def A(name, label, default, imp=S, **kw):   # an amount, 0..1, shown as % (the kit's one display for it)
    return N(name, label, 0, 1, 0.01, default, imp, display="percent", **kw)


# The brush: every setting of a stroke except where it goes (points) and what clips it (mask).
BRUSH = [
    Param.color("color", label="Colour", group="Brush", default="#202020"),
    N("size", "Size", 0.5, 2000, 0.5, 12.0, unit="px"),
    Param.choice("brush", TIPS, label="Tip", group="Brush", default="round",
                 help="round, bristle (dry brush), chalk, flat, block (square block-in), line (crisp thin line)"),
    A("opacity", "Opacity", 1.0),
    A("hardness", "Hardness", 0.5, help="0 = soft edge, 1 = hard edge"),
    Param.choice("mode", MODES, label="Mode", group="Brush", default="normal", importance=S,
                 help="normal paints over, multiply glazes, erase removes, screen / add paint light"),
    A("size_pressure", "Pressure → size", 0.8, group="Pen"),
    A("opacity_pressure", "Pressure → opacity", 0.3, group="Pen"),
    N("spacing", "Spacing", 0.02, 2, 0.01, 0.1, D, help="Distance between dabs, in tip lengths"),
    N("jitter", "Scatter", 0, 2, 0.01, 0.0, D, help="Dabs wander off the path, in tip sizes"),
    Param.toggle("follow", label="Tip turns with the stroke", group="Brush", default=True, importance=D),
    N("angle", "Tip angle", -360, 360, 1, 0.0, D, "°", IS("follow", False)),
    A("grain", "Paper grain", 0.0, D, help="How much the paper's tooth breaks up the paint"),
    A("color_jitter", "Colour drift", 0.04, D, group="Colour drift"),
    N("hue_jitter", "Hue drift", 0, 180, 0.5, 0.0, D, "°", group="Colour drift"),
    Param.toggle("smudge", label="Wet (smudge)", group="Wet", default=False, importance=D,
                 help="The brush drags the paint it passes over"),
    A("wet", "Wetness", 0.5, D, when=IS("smudge", True), group="Wet"),
    Param.toggle("pickup", label="Pick up layers below", group="Wet", default=False, importance=D,
                 valid_when=IS("smudge", True)),
    N("seed", "Seed", 0, 2**31 - 1, 1, 0, D, integer=True, group="Repeat",
      help="Same seed = the same bristles and drift; set once when the stroke is made"),
]

# Where each brush setting lives on a screen while painting: the one table the context bar and the brush panel both
# read, so nothing shows twice. "bar": above the canvas, the few changed while painting (in this order); the rest is
# the settings panel. `mode` is in the bar only as its "erase" value (Eraser, E); its other values (how the paint
# lays: multiply, screen, add) stay in the panel, and apply only while not erasing.
BAR = ("brush", "size", "color", "opacity")
BAR_VALUE = {"mode": "erase"}

FIELDS: dict[str, list[Param]] = {
    "paint": [
        Param.text("name", label="Name", default="Paint"),
        Param.choice("mode", LAYER_MODES, label="Blend", default="normal"),
        N("opacity", "Opacity", 0, 1, 0.01, 1.0, group="Layer"),
        Param.toggle("visible", label="Visible", default=True),
        Param.toggle("locked", label="Locked", default=False, importance=S, help="A locked layer refuses paint"),
    ],
    "stroke": [
        Param.points("points", label="Path", min=2, max=4, importance=D, group="Path",
                     help="[[x, y, pressure 0..1, tilt], …] in canvas px; pressure 1 when left out"),
        *BRUSH,
        Param.text("mask", label="Mask", default="", importance=S, group="Mask",
                   help="A paint mask's id: the stroke only paints inside it (empty = no mask)"),
    ],
    "fill": [       # a closed area filled with one colour, kept as its outline (fill.py): it stays sharp
        Param.points("points", label="Outline", min=2, max=3, importance=D, group="Path",
                     help="[[x, y, ring], …] in canvas px: ring 0 is the outside, 1, 2 … holes"),
        Param.color("color", label="Colour", group="Fill", default="#202020"),
        N("opacity", "Opacity", 0, 1, 0.01, 1.0, group="Fill"),
        Param.text("mask", label="Mask", default="", importance=S, group="Mask",
                   help="A paint mask's id: the fill only shows inside it (empty = no mask)"),
    ],
    "paintmask": [
        Param.points("points", label="Outline", min=2, max=2, required=False, group="Mask",
                     help="The polygon [[x, y], …] in canvas px"),
        N("feather", "Feather", 0, 500, 0.5, 0.0, unit="px", group="Mask"),
        Param.toggle("invert", label="Invert", default=False, group="Mask", help="Paint outside the outline instead"),
    ],
}
LABELS = {"paint": "Paint layer", "stroke": "Stroke", "fill": "Fill", "paintmask": "Paint mask"}


def defaults(kind: str) -> dict:
    return {p.name: p.default for p in FIELDS[kind] if p.default is not None}


def brush_defaults() -> dict:
    return {p.name: p.default for p in BRUSH}
