"""The one key shape, as a fields table: the value one field has at one time (`t` seconds; `v` a number, `c` a
colour, `d` a path's shape) and the `ease` that shapes the stretch to the next key. Both apps' "key" item type is
this list. `prop` names the field and never changes."""
from __future__ import annotations

from ..params import Param
from .after import AFTER, WORDS as AFTER_WORDS
from .easing import NAMES as EASES

_IS = lambda name, value: {"is": [name, value]}  # noqa: E731


# stiffness / damping only on a spring not written in words (an app's `rawSpring` fact: no bounce / speed on the key)
_RAW = {"all": [_IS("ease", "spring"), {"fact": "rawSpring"}]}


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
    Param.choice("after", AFTER, label="After the last key", group="Key", importance="secondary", default="stay",
                 labels=AFTER_WORDS, help="Read on a field's last key: stay, repeat the keys, back and forth, or carry on "
                 "at the speed it arrived with (after.py)"),
    _num("x1", "Curve x1", "Curve", 0, 1, 0.01, when=_IS("ease", "custom"), default=0.25),
    _num("y1", "Curve y1", "Curve", -2, 3, 0.01, when=_IS("ease", "custom"), default=0.1),
    _num("x2", "Curve x2", "Curve", 0, 1, 0.01, when=_IS("ease", "custom"), default=0.25),
    _num("y2", "Curve y2", "Curve", -2, 3, 0.01, when=_IS("ease", "custom"), default=1.0),
    _num("bounce", "Bounce", "Spring", 0, 1, 0.01, when=_IS("ease", "spring"), default=0.6),
    _num("speed", "Speed", "Spring", 0, 1, 0.01, when=_IS("ease", "spring"), default=0.5),
    Param.number("stiffness", label="Stiffness", group="Spring", min=1, max=2000, step=1, importance="deep",
                 valid_when=_RAW, default=170.0, help="The expert's spring (mass 1); bounce / speed win when set"),
    Param.number("damping", label="Damping", group="Spring", min=0, max=200, step=0.1, importance="deep",
                 valid_when=_RAW, default=12.0, help="The expert's spring; bounce / speed win when set"),
]
