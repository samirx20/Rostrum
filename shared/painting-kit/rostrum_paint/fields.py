"""The painting kit's item types and their fields: the one table. Brushes are data: every brush setting is a Param
with its range, importance and `valid_when`, so the brush panel, the stroke inspector, the MCP schema and the checks
of `stroke.add` all read the same list (rule of individuality: a setting that doesn't apply right now is absent).

A host app puts a kit **canvas** in its own item type (2D: a drawing's `frame`); a canvas holds `paints` (paint
layers, bottom first) and `paintmasks`. A paint layer holds `strokes`, in painting order.
"""
from __future__ import annotations

from rostrum_core import Param

from . import library
from .marks import MODES, TIPS
from .pictures import PAPERS, TEXTURES

LAYER_MODES = ("normal", "multiply", "screen", "add")
CANVAS_LISTS = ["paints", "paintmasks"]                  # a host's canvas type holds these
LISTS = {"paint": ["strokes"], "stroke": [], "fill": [], "paintmask": []}
HOLDS = {"paints": ("paint",), "strokes": ("stroke", "fill"), "paintmasks": ("paintmask",)}   # a fill is laid in order too
P, S, D = "primary", "secondary", "deep"
IS = lambda name, value: {"is": [name, value]}  # noqa: E731
GRAINY = {"any": [IS("brush", "chalk"), {"not": IS("grain", 0.0)}]}   # the paper shows: chalk, or any grain
TURNS = {"any": [{"not": {"any": [IS("brush", t) for t in ("round", "chalk", "line")]}},   # tips whose turn shows,
                 {"not": IS("texture", "none")}]}                                         # or a tip picture's


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
    Param.choice("texture", TEXTURES, label="Tip picture", group="Brush", default="none", importance=D,
                 help="A picture as the tip's shape (sponge, speckle, streaks, ragged, charcoal, or one loaded into the "
                      "project); it turns with the tip"),
    Param.choice("mode", MODES, label="Mode", group="Brush", default="normal", importance=S,
                 help="normal paints over, multiply glazes, erase removes, screen / add paint light"),
    A("size_pressure", "Pressure → size", 0.8, group="Pen"),
    A("opacity_pressure", "Pressure → opacity", 0.3, group="Pen"),
    A("steady", "Steadiness", 0.0, group="Pen", help="The line trails the pen and smooths a shaky hand; 0 = raw"),
    A("tilt_angle", "Tilt → angle", 0.0, D, when=TURNS, group="Pen", help="The tip turns the way the pen leans"),
    A("tilt_size", "Tilt → size", 0.0, D, group="Pen", help="The tip widens as the pen leans (shading on its side)"),
    N("taper_start", "Taper start", 0, 20, 0.1, 0.0, D, "× size", group="Pen", help="Starts thin over this many tip sizes"),
    N("taper_end", "Taper end", 0, 20, 0.1, 0.0, D, "× size", group="Pen", help="Ends thin over this many tip sizes"),
    N("spacing", "Spacing", 0.02, 2, 0.01, 0.1, D, display="percent", help="Distance between dabs, as a share of the tip's length"),
    Param.toggle("even", label="Even soft edge", group="Brush", default=True, importance=D,
                 help="Dabs come closer the softer the tip, so a soft stroke stays smooth (no rings)"),
    N("jitter", "Scatter", 0, 2, 0.01, 0.0, D, display="percent", help="Dabs wander off the path, up to this share of the tip's size"),
    A("size_jitter", "Size jitter", 0.0, D, help="Each dab up to this much smaller, at random"),
    N("angle_jitter", "Angle jitter", 0, 180, 1, 0.0, D, "°", TURNS, help="Each dab turned up to this much, at random"),
    Param.toggle("follow", label="Tip follows stroke", group="Brush", default=True, importance=D),
    N("angle", "Tip angle", -360, 360, 1, 0.0, D, "°", IS("follow", False)),
    A("grain", "Paper grain", 0.0, D, help="How much the paper's tooth breaks up the paint"),
    Param.choice("paper", PAPERS, label="Paper", group="Brush", default="tooth", importance=D, valid_when=GRAINY,
                 help="The paper's tooth; it stays put on the canvas (or moves with the layer), never with the stroke"),
    N("paper_scale", "Paper scale", 0.25, 4, 0.05, 1.0, D, "×", when=GRAINY, help="How big the paper's tooth is"),
    A("color_jitter", "Colour drift", 0.04, D, group="Colour drift"),
    N("hue_jitter", "Hue drift", 0, 180, 0.5, 0.0, D, "°", group="Colour drift"),
    Param.toggle("smudge", label="Wet (smudge)", group="Wet", default=False, importance=D,
                 help="The brush drags the paint it passes over"),
    A("wet", "Wetness", 0.5, D, when=IS("smudge", True), group="Wet",
      help="100 % only drags the paint it passes (a blender: no colour of its own); lower lays that much of the brush's colour too"),
    Param.toggle("pickup", label="Pick up layers below", group="Wet", default=False, importance=D,
                 valid_when=IS("smudge", True)),
    N("seed", "Seed", 0, 2**31 - 1, 1, 0, D, integer=True, group="Repeat",
      help="Same seed = the same bristles and drift; set once when the stroke is made"),
]


def _pictures():
    """The tip and paper choices: the built-in pictures, then the open project's own (library.py, the one list)."""
    for p in BRUSH:
        if p.name in ("texture", "paper"):
            own = library.choices("tip" if p.name == "texture" else "paper")
            p.options = [c["value"] for c in own]
            p.labels = {c["value"]: c["label"] for c in own}


library.listen(_pictures)

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
        Param.text("layer", label="Shared key", importance=D,
                   help="Links this paint layer's copies in the drawings that share paint layers (linked.py); set by "
                        "Rostrum, left out = its own id"),
    ],
    "stroke": [
        Param.points("points", label="Path", min=2, max=5, importance=D, group="Path",
                     help="[[x, y, pressure 0..1, tilt x°, tilt y°], …] in canvas px; pressure 1 and no lean when "
                          "left out (tilt: the pen's lean each way, -60..60, as Qt reports it)"),
        *BRUSH,
        Param.text("mask", label="Mask", default="", importance=S, group="Mask",
                   help="A paint mask's id: the stroke only paints inside it (empty = no mask)"),
        Param.toggle("wrap", label="Seamless", group="Path", importance=D,
                     help="The canvas's opposite edges are joined: paint that crosses an edge comes back on the other "
                          "side (wrap.py). Set when the stroke is made on a seamless canvas; left out = off"),
        Param.toggle("by_dab", label="Per-dab draws", default=True, group="Path", importance=D,
                     help="The brush's random numbers (bristles, jitter, colour drift) are drawn per dab, so the stroke "
                          "so far is the start of the finished one and the live ink can lay it in pieces "
                          "(brush.plan); a bristle or flat tip's ragged ends reach about a brush size in, not a share "
                          "of the stroke. On for new strokes; left out = the older draws, kept by strokes made before"),
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
