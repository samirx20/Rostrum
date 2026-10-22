"""What an expression may use: its error, names, the fixed list of functions and the noise formula.
Grammar and the full list: expr.py."""
from __future__ import annotations

import bisect
import math


class ExprError(ValueError):
    def __init__(self, msg: str, col: int = 0):
        super().__init__(msg)
        self.msg, self.col = msg, col

    def at(self, where: str, source: str) -> str:
        """`logo.x: column 7: unknown function "foo"   [source]` (where = item.field)."""
        return f"{where}: column {self.col}: {self.msg}   [{source}]" if self.col else f"{where}: {self.msg}   [{source}]"


CONSTS = {"pi": math.pi, "e": math.e, "true": 1.0, "false": 0.0}
VARS = {"time", "frame", "fps", "duration"}


def _hash(n: int, seed: int) -> float:
    """32-bit integer mixing only, so every machine gives the same number (-1..1)."""
    x = (n * 374761393 + seed * 668265263 + 144665) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((x ^ (x >> 16)) / 0xFFFFFFFF) * 2 - 1


def noise(x: float, seed: float = 0.0) -> float:
    """Value noise in -1..1: i = floor(x), f = x - i, u = f·f·(3 - 2f), h(i) + (h(i+1) - h(i))·u."""
    i, s = math.floor(x), int(math.floor(seed))
    f = x - i
    a, b = _hash(i, s), _hash(i + 1, s)
    return a + (b - a) * (f * f * (3 - 2 * f))


def pulse(beats: list[float], t: float, decay: float) -> float:
    """1 on each beat, falling in a straight line to 0 over `decay` seconds (0 before the first beat). `beats`: the
    project's sound's beat times, sorted (project_sound.beats)."""
    i = bisect.bisect_right(beats, t + 1e-9) - 1
    return 0.0 if i < 0 else max(0.0, 1.0 - max(0.0, t - beats[i]) / decay)


FUNCS = {"sin": (1, 1, math.sin), "cos": (1, 1, math.cos), "abs": (1, 1, abs), "sqrt": (1, 1, math.sqrt),
         "floor": (1, 1, lambda x: float(math.floor(x))), "ceil": (1, 1, lambda x: float(math.ceil(x))),
         "round": (1, 1, lambda x: float(math.floor(x + 0.5))), "min": (2, 8, min), "max": (2, 8, max),
         "clamp": (3, 3, lambda x, lo, hi: min(max(x, lo), hi)), "lerp": (3, 3, lambda a, b, p: a + (b - a) * p),
         "noise": (1, 2, noise),
         "pulse": (0, 1, None)}               # pulse(decay = 0.25): run by expr_run, which has the beats
STATIC = {"ref", "marker"}                       # their first argument is a quoted name, known before anything runs
CMPS = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
        "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
