"""The plain Python a Sound script has besides the song API: all of Python (rostrum_core/script_python.py: any import,
classes, every built-in), `math`, a seeded `random`, and `print`.

- `random` is seeded the same at the start of every run (seed 1), so a script run again writes the same notes and a
  person's edits are kept; `random.seed(n)` gives another draw, `random.Random(n)` a generator of its own.
- `print(...)` lines come back in run_script's reply (as warnings, the first 40), so a script can show what it computed.
"""
from __future__ import annotations

import math
import threading

from rostrum_core import script_python
from rostrum_core.seeded import SeededRandom

PRINT_LIMIT = script_python.PRINT_LIMIT
_printed = threading.local()


def say(message: str) -> None:
    """A note from a helper to the script's reply (the same list `print` fills); nowhere to say it outside a run."""
    if hasattr(_printed, "lines"):
        script_python.Lines(_printed.lines, PRINT_LIMIT).add(str(message))


def scope(name: str = "song.py") -> dict:
    """A fresh scope for one run: Python's built-ins, math, random seeded at 1, and an empty print list (read with `printed`)."""
    _printed.lines = []
    return {**script_python.globals_for(name, SeededRandom(1)), "math": math}


def running(name: str):
    """Around the script's exec: what it prints goes to this run's list; exit() ends it there (script_python.running)."""
    if not hasattr(_printed, "lines"):
        _printed.lines = []
    return script_python.running(_printed.lines, name, PRINT_LIMIT)


def forget_printed():
    _printed.lines = []


def printed() -> list[str]:
    """What the last run on this thread printed."""
    return list(getattr(_printed, "lines", []))
