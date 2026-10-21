"""The fields of the three outline mesh shapes (text, svg, path2d); imported into fields.py's mesh list. All three are
flat outlines the core extrudes `depth` deep (outline.py makes the outlines, compile.py sends them). Document-only:
the compiler turns them into the scene's one mesh shape "outline". Each field is valid only for the shape it belongs to.
"""
from __future__ import annotations

from rostrum_core import Param

OUTLINE_SHAPES = ["text", "svg", "path2d"]
_is = lambda name, value: {"is": [name, value]}  # noqa: E731
OUTLINE = {"any": [_is("shape", s) for s in OUTLINE_SHAPES]}
TEXT, SVG, PATH2D = _is("shape", "text"), _is("shape", "svg"), _is("shape", "path2d")
DRAWN = {"any": [SVG, PATH2D]}
FONTS = "Inter, Recursive, RobotoFlex"


def _n(name, label, lo, hi, step, unit, imp, when, default, help="", integer=False):
    return Param.number(name, label=label, group="Shape", min=lo, max=hi, step=step, unit=unit, importance=imp,
                        valid_when=when, default=default, help=help, integer=integer)


def _t(name, label, imp, when, help, default=""):
    return Param.text(name, label=label, group="Shape", importance=imp, valid_when=when, default=default, help=help)


def _face(name, label, imp, help):
    return Param.text(name, label=label, group="Material", importance=imp, valid_when=OUTLINE, default="", help=help,
                      kind="material")


FIELDS = [
    _t("text", "Text", "primary", TEXT, "The words; a new line starts a new line of text", default="Text"),
    _t("font", "Font", "primary", TEXT, f"One of the fonts that ship with Rostrum ({FONTS}), or the absolute path of a .ttf / .otf",
       default="Inter"),
    _n("size", "Size", 0.0001, 1e3, 0.001, "m", "primary", TEXT, 0.1, "The em: roughly the height of a capital is 0.7 of it"),
    _n("weight", "Weight", 1, 1000, 1, "", "secondary", TEXT, 400, "The font's weight axis (100 thin … 900 black); fonts without one need 400"),
    _n("tracking", "Tracking", -500, 5000, 1, "‰ em", "secondary", TEXT, 0.0, "Space added between letters, in thousandths of an em"),
    _n("lineHeight", "Line height", 0.1, 10, 0.01, "× size", "secondary", TEXT, 1.2, "Distance between lines of a text with new lines"),
    Param.choice("align", ["left", "center", "right"], label="Align", group="Shape", importance="secondary", valid_when=TEXT,
                 default="center", help="Which edge of the text sits on the item's origin (and how its lines line up)"),
    _t("svgFile", "SVG file", "primary", SVG, "Absolute path of an .svg; filled shapes become the outline"),
    _t("pathData", "Path data", "secondary", SVG, "SVG path data text instead of a file (M L H V C S Q T A Z, y down); used when not empty"),
    _t("doc2d", "2D item", "primary", PATH2D, "The id of a 2D item in this project folder (docs/<id>.mtn)"),
    _t("layer", "Path layer", "primary", PATH2D, "The id of a path layer inside that 2D item; its shape (fill rule included) is used"),
    _n("svgWidth", "Drawing width", 0.0001, 1e3, 0.001, "m", "primary", DRAWN, 1.0, "The drawing is scaled to be this wide", ),
    _face("frontMaterial", "Front material", "secondary", 'The face turned to the camera; "" = the material'),
    _face("bevelMaterial", "Bevel material", "deep", 'The rounded edge; "" = the front material'),
    _face("sideMaterial", "Side material", "deep", 'The straight walls; "" = the material'),
    _face("backMaterial", "Back material", "deep", 'The back face; "" = the material'),
]
