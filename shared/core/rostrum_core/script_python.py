"""Plain Python for every app's script: any import (the standard library and the venv's packages: numpy, dataclasses,
itertools …), classes and all of Python's built-ins. The script runs in the app's own process; it reaches the person's
files only if it opens them.

What stays the app's own:
- `random` (and `import random`) is a generator seeded 1 at the start of every run, so a script run again makes the same
  thing; it is a real `random.Random`, so `random.Random(7)`, `random.seed(3)`, `from random import choice` all work.
- `print(...)` (and anything else written to stdout) comes back in the reply, never on the server's own channel.
- `input()` and reads of stdin get nothing (there is no one to type); `exit()` / `sys.exit()` end the script there and
  keep what it made.

    scope = {**globals_for(name, rnd), **app_names}
    with running(lines) as run:
        exec(compile(source, name, "exec"), scope)        # SystemExit is caught: run.exited says where
"""
from __future__ import annotations

import builtins
import contextlib
import io
import sys
import threading
import traceback

from .seeded import SeededRandom

PRINT_LIMIT = 40
_lock = threading.RLock()            # sys.stdout / sys.stdin are the process's: one script swaps them at a time


def _no_input(prompt=""):
    raise RuntimeError("a script can't ask for typed input (no one is there to type); write the value in the script")


def builtins_for(rnd: SeededRandom) -> dict:
    """All of Python's built-ins; `import random` gives the run's seeded generator, every other import is Python's own."""
    real = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "random" and level == 0:
            return rnd
        return real(name, globals, locals, fromlist, level)
    return {**vars(builtins), "__import__": _import, "input": _no_input}


def globals_for(name: str, rnd: SeededRandom | None = None, file: str | None = None) -> dict:
    """A fresh module scope for one run: `__builtins__` (builtins_for), `__name__` (classes need it), `random`."""
    rnd = rnd if rnd is not None else SeededRandom(1)
    return {"__builtins__": builtins_for(rnd), "__name__": "__main__", "__file__": file or name, "random": rnd}


class Lines(io.TextIOBase):
    """A text stream whose whole lines go into `lines` (the first PRINT_LIMIT, then one line saying more were left out)."""

    def __init__(self, lines: list[str], limit: int = PRINT_LIMIT):
        self.lines, self.limit, self._part = lines, limit, ""

    def writable(self) -> bool:
        return True

    def write(self, s: str) -> int:
        self._part += str(s)
        *done, self._part = self._part.split("\n")
        for line in done:
            self.add(line)
        return len(s)

    def add(self, line: str) -> None:
        if len(self.lines) < self.limit:
            self.lines.append(line)
        elif len(self.lines) == self.limit:
            self.lines.append("… (more print lines left out)")

    def finish(self) -> None:
        if self._part:
            self.add(self._part)
            self._part = ""


class Run:
    """What `running` saw: `exited` = 'line N' (or '') when the script called exit() / sys.exit()."""
    exited: str | None = None


@contextlib.contextmanager
def running(lines: list[str], name: str | None = None, limit: int = PRINT_LIMIT):
    """Run a script's exec inside: stdout goes into `lines`, stdin is empty, exit() ends the script without an error.
    `name`: the script's file name, to say which line called exit()."""
    out, run = Lines(lines, limit), Run()
    with _lock:
        old_in = sys.stdin
        sys.stdin = io.StringIO("")
        try:
            with contextlib.redirect_stdout(out):
                try:
                    yield run
                except SystemExit as e:
                    rows = [fr for fr in traceback.extract_tb(e.__traceback__) if name is None or fr.filename == name]
                    run.exited = f"line {rows[-1].lineno}" if rows else ""
        finally:
            sys.stdin = old_in
            out.finish()


def exit_note(run: Run) -> list[str]:
    """The reply line for a script that ended at exit(); none when it ran to its end."""
    if run.exited is None:
        return []
    return [f"the script ended at exit(){' on ' + run.exited if run.exited else ''}; what it made before that is kept"]
