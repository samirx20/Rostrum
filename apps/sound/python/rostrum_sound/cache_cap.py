"""The sound engine's share of Rostrum's one cache, kept under the one cap (docs/RELEASE.md line 16).

The engine keeps loose files in `<cache root>/sound/<sub>/` (tracks, media, stretch, plugin: engine
`mix/cache.rs`); a hit renews a file's time. rostrum_core.cache trims only its own entries (folders with an
`entry.json`), so nobody trimmed these. After a render, the oldest engine files go until the whole root (its
entries plus these files) is under the cap; a file used in the last 15 minutes stays, and a write the engine never
finished (`*.tmp`, an ended process) goes once it is an hour old.

    cache_cap.trim()             # -> bytes freed (tests pass root= and cap=)
    cache_cap.after_render()     # the same, at most once a minute, off the caller's thread
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from rostrum_core.cache import KEEP_RECENT_S, Cache

STALE_TMP_S = 3600
_last = [0.0]
_lock = threading.Lock()


def engine_files(root: Path) -> list[tuple[float, int, Path]]:
    """(last used, bytes, file) of every engine cache file."""
    out = []
    for p in (Path(root) / "sound").rglob("*"):
        try:
            if p.is_file():
                st = p.stat()
                out.append((st.st_mtime, st.st_size, p))
        except OSError:                       # removed meanwhile by another process
            continue
    return out


def trim(root=None, cap: int | None = None, now: float | None = None) -> int:
    store = Cache(root, cap)
    now = time.time() if now is None else now
    files = sorted(engine_files(store.root))
    total, freed = store.stats()["bytes"] + sum(f[1] for f in files), 0
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


def after_render(min_gap_s: float = 60):
    with _lock:
        if time.monotonic() - _last[0] < min_gap_s:
            return
        _last[0] = time.monotonic()
    threading.Thread(target=trim, daemon=True, name="sound cache trim").start()
