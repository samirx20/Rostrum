"""The one key shape, as a fields table: the value one field has at one time (`t` seconds; `v` a number, `c` a
colour, `d` a path's shape) and the `ease` that shapes the stretch to the next key. Both apps' "key" item type is
this list. `prop` names the field and never changes."""
from __future__ import annotations

from ..params import Param
from .easing import NAMES as EASES

_IS = lambda name, value: {"is": [name, value]}  # noqa: E731


def _num(name, label, group, lo, hi, step, unit="", when=None, default=0.0):
    return Param.number(name, label=label, group=group, min=lo, max=hi, step=step, unit=unit, importance="primary",
                        valid_when=when, default=default)


KEY_FIELDS = [
    Param.number("t", label="Time", group="Key", min=-36000, max=36000, step=0.001, unit="s", importance="primary",
                 default=0.0, markers=True, help="Seconds in its owner's time, or a shared marker (\"#drop+0.2\", "
                 "marked.py); before 0 / before the owner's start is a pre-roll"),
    _num("v", "Value", "Key", -1e9, 1e9, 0.01, when={"fact": "number"}),
    Param.color("c", label="Value", group="Key", importance="primary", valid_when={"fact": "color"}, default="#ffffff"),
    Param.text("d", label="Shape", group="Key", importance="primary", valid_when={"fact": "shape"}, default="",
               help="Path data; the engine morphs it into the next key's shape"),
    Param.choice("ease", list(EASES), label="Ease", group="Key", importance="primary", default="smooth"),
    _num("x1", "Curve x1", "Curve", 0, 1, 0.01, when=_IS("ease", "custom"), default=0.25),
    _num("y1", "Curve y1", "Curve", -2, 3, 0.01, when=_IS("ease", "custom"), default=0.1),
    _num("x2", "Curve x2", "Curve", 0, 1, 0.01, when=_IS("ease", "custom"), default=0.25),
    _num("y2", "Curve y2", "Curve", -2, 3, 0.01, when=_IS("ease", "custom"), default=1.0),
    _num("stiffness", "Stiffness", "Spring", 1, 2000, 1, when=_IS("ease", "spring"), default=170.0),
    _num("damping", "Damping", "Spring", 0, 200, 0.1, when=_IS("ease", "spring"), default=12.0),
]
