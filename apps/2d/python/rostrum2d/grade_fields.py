"""Colour effects every layer has (merged into fields.py TRANSFORM): adjust (exposure, contrast, saturation,
temperature, tint, hue), levels, curves and a .cube LUT. Each turns on with its own toggle (or, for the LUT, a
file), and its controls are absent until then (rule of individuality).

The engine turns them into one grade (engine/render/src/scene/grade.rs → the rostrum-color grade → one SkSL colour
filter on the layer); a bad curve or .cube file is refused when the scene loads, naming the layer, field and line.
Curve points are text, "x,y x,y …" from 0 to 1, what agents write; on screen the kit's curve control (CurveField) edits them.
"""
from __future__ import annotations

from rostrum_core import Param

G = "Colour"
ADJUST, LEVELS, CURVES = ({"is": [n, True]} for n in ("adjust", "levels", "curves"))
HAS_LUT = {"not": {"is": ["lut", ""]}}
STRAIGHT = "0,0 1,1"
POINTS_HELP = ('Points "x,y x,y …" from 0 to 1: x = how bright going in, y = how bright coming out. '
               'At least two, x rising; "0,0 1,1" changes nothing')


def _n(name, label, lo, hi, step, default, when, unit="", imp="secondary", help=""):
    return Param.number(name, label=label, group=G, min=lo, max=hi, step=step, unit=unit, importance=imp,
                        valid_when=when, default=default, help=help)


def _t(name, label, help):
    return Param.toggle(name, label=label, group=G, importance="secondary", default=False, help=help)


def _curve(name, label, imp="secondary"):
    return Param.text(name, label=label, group=G, importance=imp, valid_when=CURVES, default=STRAIGHT, help=POINTS_HELP,
                      control="curve")


COLOUR = [
    _t("adjust", "Adjust colour", "Exposure, contrast, saturation, temperature, tint and hue"),
    _n("exposure", "Exposure", -10, 10, 0.01, 0.0, ADJUST, "stops", help="+1 = twice the light, −1 = half"),
    _n("contrast", "Contrast", 0, 4, 0.01, 1.0, ADJUST, "×", help="1 = unchanged; about mid grey"),
    _n("saturation", "Saturation", 0, 4, 0.01, 1.0, ADJUST, "×", help="0 = grey, 1 = unchanged, 2 = twice as rich"),
    _n("temperature", "Temperature", -5, 5, 0.01, 0.0, ADJUST, help="+ warmer (orange), − cooler (blue)"),
    _n("tint", "Tint", -5, 5, 0.01, 0.0, ADJUST, imp="deep", help="+ greener, − more magenta"),
    _n("hue", "Hue shift", -180, 180, 0.1, 0.0, ADJUST, "°", "deep", help="Turns every colour round the colour wheel"),
    _t("levels", "Levels", "Set the black and white points and the middle brightness"),
    _n("inBlack", "Black in", 0, 1, 0.001, 0.0, LEVELS, help="This brightness and below becomes black"),
    _n("inWhite", "White in", 0, 1, 0.001, 1.0, LEVELS, help="This brightness and above becomes white"),
    _n("gamma", "Middle", 0.1, 10, 0.01, 1.0, LEVELS, help="Above 1 brightens the middle tones, below 1 darkens them"),
    _n("outBlack", "Black out", 0, 1, 0.001, 0.0, LEVELS, imp="deep", help="How bright black comes out (raise it to fade)"),
    _n("outWhite", "White out", 0, 1, 0.001, 1.0, LEVELS, imp="deep", help="How bright white comes out"),
    _t("curves", "Curves", "Reshape brightness, for all channels or red, green and blue alone (after levels)"),
    _curve("curve", "Curve"),
    _curve("curveR", "Red curve", "deep"),
    _curve("curveG", "Green curve", "deep"),
    _curve("curveB", "Blue curve", "deep"),
    Param.text("lut", label="LUT file", group=G, importance="deep", default="", control="file",
               filters=["Colour look-up tables (*.cube)"],
               help="A .cube colour look-up table (absolute path), applied last. Empty = none"),
    _n("lutMix", "LUT amount", 0, 1, 0.01, 1.0, HAS_LUT, help="0 = none of the LUT, 1 = all of it"),
]
