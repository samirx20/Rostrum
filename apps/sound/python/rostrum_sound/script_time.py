"""Beat arithmetic in a script: `bar(5) + beats(2)`, `beat(i * 4) - beats(0.5)`, `beats(1) * 3`.

`beat(n)` / `bar(n)` give a time on the beat grid (`{"beat": n}`), `beats(n)` a length (`{"beats": n}`). They stay plain
document values (a dict subclass: the document and the engine see `{"beat": n}`), and add up the way music does:

    time + length = time     time - length = time     time - time = length
    length ± length = length     length * k = length     length / k = length
    times compare with times (bar(5) < beat(20)), lengths with lengths

A bare number is seconds everywhere else, so `bar(5) + 0.5` would mix beats and seconds: that is refused with the two
forms that say what was meant (never guessed).
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes


def _refuse(a, op, b):
    shown = f"{_show(a)} {op} {_show(b)}"
    if op in ("<", "<=", ">", ">="):
        why = "a time compares with a time and a length with a length (a bare number is seconds)"
        accepted = ["bar(5) < beat(20)", "beats(2) <= beats(4)", "t[\"beat\"] < 20 (the beat number itself)"]
    elif isinstance(a, str) or isinstance(b, str):
        why = "a marker is a moment in seconds, so beats after it have no one meaning (the tempo there decides)"
        accepted = ['"#drop+0.5" (seconds after a marker)', "a marker on the grid: marker(\"drop\", at=bar(5)); then bar(5) + beats(1)"]
    elif isinstance(a, (int, float)) or isinstance(b, (int, float)):
        why = "a bare number is seconds, so a beat time plus a number mixes beats and seconds"
        accepted = ["bar(5) + beats(0.5) (half a beat later)", "beat(16.5) (a beat number)", "18.5 (seconds, a bare number)"]
    else:
        why = "two times don't add up to a time"
        accepted = ["bar(5) + beats(2) (a time plus a length)", "bar(9) - bar(5) (the length between two times)"]
    raise RostrumError(codes.BAD_ARGUMENT, "beat arithmetic", shown,
                       f"can't be worked out: {why}",
                       accepted, "beat()/bar() are times on the beat grid, beats(n) is a length in beats, a bare number is seconds.")


def _ordered(kind, key):
    """<, <=, >, >= between two of the same kind; against anything else, the loud refusal."""
    def make(op, fn):
        def compare(self, other):
            if isinstance(other, kind):
                return fn(self[key], other[key])
            _refuse(self, op, other)
        return compare
    return {"__lt__": make("<", lambda a, b: a < b), "__le__": make("<=", lambda a, b: a <= b),
            "__gt__": make(">", lambda a, b: a > b), "__ge__": make(">=", lambda a, b: a >= b)}


def _show(v) -> str:
    if isinstance(v, Beat):
        return f"beat({v['beat']:g})"
    if isinstance(v, Beats):
        return f"beats({v['beats']:g})"
    return repr(v)


class Beat(dict):
    """A time on the beat grid, `{"beat": n}` (0-based)."""

    def __init__(self, n):
        super().__init__(beat=n)

    def __add__(self, other):
        if isinstance(other, Beats):
            return Beat(self["beat"] + other["beats"])
        _refuse(self, "+", other)

    __radd__ = __add__

    def __sub__(self, other):
        if isinstance(other, Beats):
            return Beat(self["beat"] - other["beats"])
        if isinstance(other, Beat):
            return Beats(self["beat"] - other["beat"])
        _refuse(self, "-", other)

    def __rsub__(self, other):
        _refuse(other, "-", self)


class Beats(dict):
    """A length in beats, `{"beats": n}`."""

    def __init__(self, n):
        super().__init__(beats=n)

    def __add__(self, other):
        if isinstance(other, Beats):
            return Beats(self["beats"] + other["beats"])
        if isinstance(other, Beat):
            return Beat(other["beat"] + self["beats"])
        _refuse(self, "+", other)

    def __radd__(self, other):
        if isinstance(other, (Beat, Beats)):
            return self + other
        _refuse(other, "+", self)

    def __sub__(self, other):
        if isinstance(other, Beats):
            return Beats(self["beats"] - other["beats"])
        _refuse(self, "-", other)

    def __rsub__(self, other):
        _refuse(other, "-", self)

    def __mul__(self, k):
        if isinstance(k, (int, float)) and not isinstance(k, bool):
            return Beats(self["beats"] * k)
        _refuse(self, "*", k)

    __rmul__ = __mul__

    def __truediv__(self, k):
        if isinstance(k, (int, float)) and not isinstance(k, bool):
            return Beats(self["beats"] / k)
        _refuse(self, "/", k)


for _cls, _key in ((Beat, "beat"), (Beats, "beats")):
    for _name, _fn in _ordered(_cls, _key).items():
        setattr(_cls, _name, _fn)
