"""Clean up the per-run scratch folders (`<cache>/screensound/<pid>`, `<cache>/screen2d/<pid>`) that killed runs left behind.

A screen's own folder is removed when it closes normally; a killed one never gets to. `sweep` removes the folders named by a
process id whose folder is older than a day and whose id no running process holds. `sweep_later` does it once, on a
background thread, well after the window is up, so it never costs the start (as the compiled-QML cache's trim, H66)."""
from __future__ import annotations

import os
import shutil
import threading
import time
from pathlib import Path

MAX_AGE_S = 24 * 3600
START_QUIET_S = 45


def running(pid: int) -> bool:
    """Is a process with this id alive? (Windows: os.kill would end it, so the handle is asked instead.)"""
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)            # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return k32.GetLastError() == 5                 # access denied: it exists, it is not ours
        try:
            code = ctypes.c_ulong()
            return bool(k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259     # STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def sweep(parent, max_age_s: float = MAX_AGE_S, now: float | None = None) -> int:
    """Remove the pid-named folders in `parent` older than `max_age_s` that no running process owns. Returns how many went."""
    now = time.time() if now is None else now
    gone = 0
    try:
        with os.scandir(parent) as it:
            old = [e for e in it if e.name.isdigit() and e.is_dir(follow_symlinks=False) and now - e.stat().st_mtime > max_age_s]
    except OSError:
        return 0
    for e in old:
        if int(e.name) == os.getpid() or running(int(e.name)):
            continue
        shutil.rmtree(e.path, ignore_errors=True)
        gone += not os.path.exists(e.path)
    return gone


def sweep_later(parent, delay_s: float = START_QUIET_S) -> None:
    """Sweep once, `delay_s` after now, on a daemon thread."""
    t = threading.Timer(delay_s, sweep, args=(parent,))
    t.daemon = True
    t.start()
