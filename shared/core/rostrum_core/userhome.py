"""Where the person's settings live: the one source of truth (Open recent, settings.json, sound.json ...).

A person's normal start keeps them in ~/.rostrum. A *scripted* run (an agent's screenshot or step run, a layout check,
a test, anything running from a team worktree) must never touch them, or its throwaway projects fill the person's
"Open recent" and double-clicking the app opens a test. A scripted run gets a scratch home instead, removed at exit.

    scripted()    why this run is scripted (a short reason), or None for a person's normal start
    home()        the settings root: ~/.rostrum, or the scratch home of a scripted run
    locked(path)  hold an exclusive lock around a read-modify-write of one settings file (two windows at once)

A scripted run is one with: ROSTRUM_SCRIPTED_HOME set (a parent run chose a scratch home; children share it), or
--shot / --step / --check-layout in the arguments, or pytest running, or this code living under .t3/worktrees.
ROSTRUM_REAL_HOME=1 forces the real home (a person deliberately running from a worktree).
"""
from __future__ import annotations

import atexit
import contextlib
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from .errors import RostrumError, codes

FLAGS = ("--shot", "--step", "--check-layout")
WAIT_S = 5.0
_made: Path | None = None            # the scratch home this process created (and removes at exit)


def scripted() -> str | None:
    if os.environ.get("ROSTRUM_REAL_HOME") == "1":
        return None
    if os.environ.get("ROSTRUM_SCRIPTED_HOME"):
        return "ROSTRUM_SCRIPTED_HOME is set"
    flag = next((a for a in sys.argv[1:] if a.split("=", 1)[0] in FLAGS), None)
    if flag:
        return flag.split("=", 1)[0]
    if "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST"):
        return "pytest"
    here = str(Path(__file__).resolve()).lower()
    if "\\.t3\\worktrees\\" in here or "/.t3/worktrees/" in here:
        return "running from a team worktree"
    return None


def _cleanup(folder: Path) -> None:
    shutil.rmtree(folder, ignore_errors=True)


def home() -> Path:
    global _made
    reason = scripted()
    if reason is None:
        return Path.home() / ".rostrum"
    if os.environ.get("ROSTRUM_SCRIPTED_HOME"):
        return Path(os.environ["ROSTRUM_SCRIPTED_HOME"])
    _made = Path(tempfile.mkdtemp(prefix="rostrum-run-"))
    os.environ["ROSTRUM_SCRIPTED_HOME"] = str(_made)
    atexit.register(_cleanup, _made)
    print(f"scripted run ({reason}): settings and Open recent kept in {_made}, not the person's", file=sys.stderr)
    return _made


def _try_lock(fh) -> bool:
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(fh) -> None:
    if os.name == "nt":
        import msvcrt
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fh, fcntl.LOCK_UN)


@contextlib.contextmanager
def locked(path):
    """Exclusive lock on `<path>.lock` while the block runs; waits up to ~5 s, then fails loudly naming the file.
    Not re-entrant: take it once, around the whole read-modify-write."""
    path = Path(path)
    lock = path.with_name(path.name + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a+b") as fh:
        if lock.stat().st_size == 0:
            fh.write(b"\0")
            fh.flush()
        deadline = time.monotonic() + WAIT_S
        while not _try_lock(fh):
            if time.monotonic() > deadline:
                raise RostrumError(codes.INTERNAL, "settings", str(path), "is being changed by another Rostrum window",
                                   hint=f"Waited {WAIT_S:.0f} s for {lock}; close the other window or delete that file.")
            time.sleep(0.05)
        try:
            yield
        finally:
            _unlock(fh)
