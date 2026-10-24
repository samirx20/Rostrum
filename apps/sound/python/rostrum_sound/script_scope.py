"""The plain Python a Sound script may use besides the song API: safe builtins, `math`, a seeded `random`, and `print`.

- `import math` / `import random` give the modules already in scope; any other import is refused, naming what is there.
- `random` is seeded the same at the start of every run (seed 1), so a script run again writes the same notes and a
  person's edits are kept; `random.seed(n)` gives another draw.
- `print(...)` lines come back in run_script's reply (as warnings, the first 40), so a script can show what it computed.
"""
from __future__ import annotations

import builtins
import math
import random as _random
import threading

NAMES = ("range", "len", "min", "max", "abs", "round", "enumerate", "zip", "list", "dict", "tuple", "set", "float",
         "int", "str", "bool", "sorted", "sum", "reversed", "isinstance", "hasattr", "any", "all", "map", "filter",
         "divmod", "pow", "ValueError", "KeyError", "IndexError", "TypeError", "Exception")
MODULES = {"math": math}
PRINT_LIMIT = 40
_printed = threading.local()


def _import(name, *args, **kw):
    if name in _printed.modules:
        return _printed.modules[name]
    raise ImportError(f"scripts can't import {name!r}; math and random (seeded) are already there, and range, len, "
                      "min, max, round, sorted, sum, isinstance, any, all …")


def _print(*args, sep=" ", end="", **kw):
    lines = _printed.lines
    if len(lines) < PRINT_LIMIT:
        lines.append(sep.join(str(a) for a in args))
    elif len(lines) == PRINT_LIMIT:
        lines.append("… (more print lines left out)")


def scope() -> dict:
    """A fresh scope for one run: builtins, math, random seeded at 1, and an empty print list (read with `printed`)."""
    rnd = _random.Random(1)
    _printed.lines = []
    _printed.modules = {**MODULES, "random": rnd}
    safe = {n: getattr(builtins, n) for n in NAMES}
    return {"__builtins__": {**safe, "__import__": _import, "print": _print}, "math": math, "random": rnd}


def forget_printed():
    _printed.lines = []


def printed() -> list[str]:
    """What the last run on this thread printed."""
    return list(getattr(_printed, "lines", []))
