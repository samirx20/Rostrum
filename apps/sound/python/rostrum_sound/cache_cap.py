"""The sound engine's share of Rostrum's one cache, kept under the one cap (docs/RELEASE.md line 16).

The engine keeps loose files in `<cache root>/sound/<sub>/` (tracks, media, stretch, plugin: engine
`mix/cache.rs`); a hit renews a file's time. rostrum_core.cache trims only its own entries (folders with an
`entry.json`), so nobody trimmed these. After a render, the oldest engine files go until the whole root (its
entries plus these files) is under the cap; a file used in the last 15 minutes stays, and a write the engine never
finished (`*.tmp`, an ended process) goes once it is an hour old.

    cache_cap.trim()             # -> bytes freed (tests pass root= and cap=)
    cache_cap.after_render()     # the same, at most once a minute, off the caller's thread, and never in the first
                                 # START_QUIET_S of the process (the window is starting: a scan then costs the start)
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from rostrum_core.cache import KEEP_RECENT_S, Cache

STALE_TMP_S = 3600
START_QUIET_S = 45
_born = time.monotonic()
_last = [0.0]
_lock = threading.Lock()


def engine_files(root: Path) -> list[tuple[float, int, Path]]:
    """(last used, bytes, file) of every engine cache file. os.scandir hands over each file's size and time with
    the listing itself (no stat call per file), so a few thousand files cost milliseconds."""
    out, todo = [], [str(Path(root) / "sound")]
    while todo:
        try:
            with os.scandir(todo.pop()) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            todo.append(e.path)
                        elif e.is_file():
                            st = e.stat()
                            out.append((st.st_mtime, st.st_size, Path(e.path)))
                    except OSError:               # removed meanwhile by another process
                        continue
        except OSError:                           # the folder is not there (yet) or went meanwhile
            continue
    return out


def trim(root=None, cap: int | None = None, now: float | None = None) -> int:
    store = Cache(root, cap)
    now = time.time() if now is None else now
    files = sorted(engine_files(store.root))
    # the entries are read gently (a pause every few: this runs on a thread beside the window, and 12,000 entry.json
    # reads in one go held the interpreter, so a click that came meanwhile waited ~0.4 s for its turn)
    total, freed = sum(e[1] for e in store.entries(gently=True)) + sum(f[1] for f in files), 0
    for used, size, p in files:
        stale_tmp = p.suffix == ".tmp" and now - used > STALE_TMP_S
        if (total <= store.cap or now - used < KEEP_RECENT_S) and not stale_tmp:
            continue
        try:
            p.unlink()
        except OSError:                       # in use by a render right now: next time
            continue
        total, freed = total - size, freed + size
    return freed


def after_render(min_gap_s: float = 60, quiet_s: float = START_QUIET_S):
    """A render ends: trim, but only once the process has been up `quiet_s` (the first renders are the start's own)."""
    with _lock:
        now = time.monotonic()
        if now - _last[0] < min_gap_s or now - _born < quiet_s:
            return
        _last[0] = now
    threading.Thread(target=trim, daemon=True, name="sound cache trim").start()
