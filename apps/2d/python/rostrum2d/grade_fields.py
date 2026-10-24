"""Colour effects (merged into fields.py): adjust (exposure, contrast, saturation, temperature, tint, hue), levels,
curves and a .cube look file. Each is its own group that turns on with its own toggle (or, for the look file, a file),
so its name in the settings panel adds it in one click ("+ Levels"), and its controls are absent until then (rule of
individuality). They apply only where there is a picture to grade (`colour(when)`: pictures, videos, 3D renders,
drawings and groups always; a shape or path only while it is filled with a picture; a text never): grading a flat
colour is choosing it twice.

The engine turns them into one grade (engine/render/src/scene/grade.rs → the rostrum-color grade → one SkSL colour
filter on the layer); a bad curve or .cube file is refused when the scene loads, naming the layer, field and line.
Curve points are text, "x,y x,y …" from 0 to 1, what agents write; on screen the kit's curve control (CurveField) edits them.
"""
from __future__ import annotations

from rostrum_core import Param

ADJUST, LEVELS, CURVES = ({"is": [n, True]} for n in ("adjust", "levels", "curves"))
HAS_LUT = {"not": {"is": ["lut", ""]}}
STRAIGHT = "0,0 1,1"
POINTS_HELP = ('Points "x,y x,y …" from 0 to 1: x = how bright going in, y = how bright coming out. '
               'At least two, x rising; "0,0 1,1" changes nothing')


def colour(when=None) -> list[Param]:
    """The colour effects, each valid only where `when` holds too (None: wherever the layer is)."""
    def on(cond):
        return cond if when is None else {"all": [when, cond]}

    def n(name, label, group, lo, hi, step, default, cond, unit="", imp="secondary", help=""):
        return Param.number(name, label=label, group=group, min=lo, max=hi, step=step, unit=unit, importance=imp,
                            valid_when=on(cond), default=default, help=help)

    def t(name, label, help):
        return Param.toggle(name, label=label, group=label, importance="secondary", default=False, help=help, valid_when=when)

    def curve(name, label, imp="secondary"):
        return Param.text(name, label=label, group="Curves", importance=imp, valid_when=on(CURVES), default=STRAIGHT,
                          help=POINTS_HELP, control="curve")

    A, L = "Adjust colour", "Levels"
    return [
        t("adjust", A, "Exposure, contrast, saturation, temperature, tint and hue"),
        n("exposure", "Exposure", A, -10, 10, 0.01, 0.0, ADJUST, "stops", help="+1 = twice the light, −1 = half"),
        n("contrast", "Contrast", A, 0, 4, 0.01, 1.0, ADJUST, "×", help="1 = unchanged; about mid grey"),
        n("saturation", "Saturation", A, 0, 4, 0.01, 1.0, ADJUST, "×", help="0 = grey, 1 = unchanged, 2 = twice as rich"),
        n("temperature", "Temperature", A, -5, 5, 0.01, 0.0, ADJUST, help="+ warmer (orange), − cooler (blue)"),
        n("tint", "Tint", A, -5, 5, 0.01, 0.0, ADJUST, imp="deep", help="+ greener, − more magenta"),
        n("hue", "Hue shift", A, -180, 180, 0.1, 0.0, ADJUST, "°", "deep", help="Turns every colour round the colour wheel"),
        t("levels", L, "Set the black and white points and the middle brightness"),
        n("inBlack", "Black in", L, 0, 1, 0.001, 0.0, LEVELS, help="This brightness and below becomes black"),
        n("inWhite", "White in", L, 0, 1, 0.001, 1.0, LEVELS, help="This brightness and above becomes white"),
        n("gamma", "Middle", L, 0.1, 10, 0.01, 1.0, LEVELS, help="Above 1 brightens the middle tones, below 1 darkens them"),
        n("outBlack", "Black out", L, 0, 1, 0.001, 0.0, LEVELS, imp="deep", help="How bright black comes out (raise it to fade)"),
        n("outWhite", "White out", L, 0, 1, 0.001, 1.0, LEVELS, imp="deep", help="How bright white comes out"),
        t("curves", "Curves", "Reshape brightness, for all channels or red, green and blue alone (after levels)"),
        curve("curve", "Curve"),
        curve("curveR", "Red curve", "deep"),
        curve("curveG", "Green curve", "deep"),
        curve("curveB", "Blue curve", "deep"),
        Param.text("lut", label="Look file", group="Look file", importance="deep", default="", control="file",
                   filters=["Colour looks (*.cube)"], valid_when=when,
                   help="A .cube colour look (a LUT, absolute path), applied last. Empty = none"),
        n("lutMix", "Look amount", "Look file", 0, 1, 0.01, 1.0, HAS_LUT, help="0 = none of the look, 1 = all of it"),
    ]


COLOUR = colour()       # every colour field by name (ops_look.py copies them as part of a look)
