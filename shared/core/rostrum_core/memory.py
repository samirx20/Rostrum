"""Free memory on this computer, and the turn a model job waits for before it loads (voice, speech words, the phone
model for lip sync, clean-up). One model job loads at a time on the machine, across every app and process (a lock file
the system frees when its process ends), and it starts only when enough memory is free. Both are waited for, a
bounded time (ROSTRUM_MODEL_WAIT_S, default 300 s), with `waiting(words)` told every few seconds; when the time runs
out the job fails plainly (NO_MEMORY), naming what it needed and what was free. A laptop shared with other work used to
refuse a voice outright when memory was short for a moment (2D final critic, F5-1: five failed calls).

    with memory.turn("voice", "voice generation", 2.5, waiting=print):
        ...load the model, run it, release it...
"""
from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from .errors import RostrumError, codes

POLL_S = 2.0


def wait_s() -> float:
    return float(os.environ.get("ROSTRUM_MODEL_WAIT_S") or 300)


def free_gb() -> float | None:
    """Free physical memory in GB (None where it can't be read)."""
    if os.name != "nt":
        return None
    import ctypes

    class M(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                    ("avail", ctypes.c_ulonglong), *[(f"x{i}", ctypes.c_ulonglong) for i in range(5)]]
    m = M()
    m.len = ctypes.sizeof(M)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.avail / 2 ** 30


def _say(words):
    print(f"rostrum: {words}", file=sys.stderr, flush=True)     # stderr: an MCP server's stdout is its protocol


def gate(where: str, what: str, need_gb: float, wait: float | None = None, waiting=None, *, free=free_gb,
         sleep=time.sleep, clock=time.monotonic) -> float | None:
    """Wait until `need_gb` is free (up to `wait` seconds, default wait_s()), then return what is free. Never frees in
    time: NO_MEMORY, said plainly."""
    limit, t0, told = wait_s() if wait is None else wait, clock(), None
    say = waiting or _say
    while True:
        f = free()
        if f is None or f >= need_gb:
            return f
        waited = clock() - t0
        if waited >= limit:
            raise RostrumError(codes.NO_MEMORY, where, what,
                               f"needs about {need_gb} GB of free memory; {f:.1f} GB was still free after waiting "
                               f"{waited:.0f} s", hint="Close other programs (or wait for other work to finish) and try "
                               "again; ROSTRUM_MODEL_WAIT_S sets how long a job waits.")
        if told is None or clock() - told >= 10 or waiting:
            say(f"waiting for memory: {what} needs about {need_gb} GB, {f:.1f} GB is free ({waited:.0f} s)")
            told = clock()
        sleep(max(0.01, min(POLL_S, limit - waited)))


def _turn_file() -> Path:
    base = Path(os.environ.get("ROSTRUM_DATA") or Path.home() / ".rostrum") / "locks"
    base.mkdir(parents=True, exist_ok=True)
    return base / "model-turn.lock"


def _try_lock(fh) -> bool:
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(fh):
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    finally:
        fh.close()


@contextmanager
def turn(where: str, what: str, need_gb: float, wait: float | None = None, waiting=None, *, free=free_gb,
         sleep=time.sleep, clock=time.monotonic, lock_file=None):
    """Hold the machine's one model turn for the with-block: wait for it (another model job is running), then for
    the memory (`gate`), together at most `wait` seconds."""
    limit, t0, told = wait_s() if wait is None else wait, clock(), None
    say = waiting or _say
    fh = open(lock_file or _turn_file(), "a+b")
    while not _try_lock(fh):
        waited = clock() - t0
        if waited >= limit:
            fh.close()
            raise RostrumError(codes.NO_MEMORY, where, what,
                               f"waited {waited:.0f} s for another model job on this computer to finish",
                               hint="Try again when it is done; ROSTRUM_MODEL_WAIT_S sets how long a job waits.")
        if told is None or clock() - told >= 10 or waiting:
            say(f"waiting for its turn: another model job is running ({waited:.0f} s)")
            told = clock()
        sleep(max(0.01, min(POLL_S, limit - waited)))
    try:
        gate(where, what, need_gb, max(0.0, limit - (clock() - t0)), waiting, free=free, sleep=sleep, clock=clock)
        yield
    finally:
        _unlock(fh)
