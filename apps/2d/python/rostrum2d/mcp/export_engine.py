"""The exports' held engine: one engine process kept between exports of a session (apart from the looks' one, warm.py,
so looks go on while an export draws). Its drawing workers stay alive in it between export requests and between
exports (engine export_pool.rs), so a re-export starts drawing at once instead of starting a process, loading the scene
and making each worker's page and GL context again. An export that finds it busy (a second export job at the same
time) gets an engine of its own for that export, as before. Cancel (run_stop) kills it; the next export starts a new
one. It ends with the server (atexit)."""
from __future__ import annotations

import atexit
import threading
from contextlib import contextmanager

_lock = threading.Lock()
_engine = None


@contextmanager
def engine():
    """The held export engine (kept after the export), or a fresh one closed after it when the held one is busy."""
    global _engine
    from rostrum2d.engine import Engine
    if not _lock.acquire(blocking=False):
        with Engine() as own:
            yield own
        return
    try:
        if _engine is None or _engine._stopped is not None:
            _engine = Engine()
        yield _engine
    finally:
        _lock.release()


@atexit.register
def close():
    global _engine
    with _lock:
        if _engine is not None:
            _engine.close()
            _engine = None
