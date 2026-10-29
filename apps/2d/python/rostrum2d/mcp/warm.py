"""The looks' one held engine: look_frame, sheets, run_script's look, look_at and the review draw through one engine
process kept between calls, holding the scene. A look after an edit sends the engine only the nodes the edit made
(scene_keep.Keeper + scene_change: the screen's own path), so a single frame costs the frame, not a process start and a
whole scene load (5-10 s on a 70 s film before; ~1 s now).

The scene held is the whole composition (span 0..its end), whatever the call draws: the same description every
look, so the keeper reuses it. Paint pictures not made yet are made first, side by side, as describe does. Exports
start their own engine (a job that runs while the agent keeps looking).

One lock: one look draws at a time (a sheet's job and a quick look_frame never mix their frames in one engine). An
engine that died restarts itself on the next request (engine.py); the process ends with the server (atexit).
"""
from __future__ import annotations

import atexit
import threading
from contextlib import contextmanager

from rostrum_core import markers as M

from rostrum2d import drawing
from rostrum2d.scene_keep import Keeper

_lock = threading.RLock()
_engine = None
_keeper = Keeper()


def scene(doc, comp_id: str, duration: float) -> dict:
    """The composition's whole description as it is now, made again only where the document changed since the last look."""
    with _lock:
        args = (doc.data, comp_id, M.times(doc.folder), doc.folder, (0.0, duration))
        jobs: list = []
        got = _keeper.describe(*args, later=jobs)
        if jobs:
            drawing.make_all(jobs, None, None)      # paint pictures first (kept by content), then described with them
            got = _keeper.describe(*args, later=[])
        if got.get("warnings"):                     # a placeholder (a 3D render not made yet) may be ready next time
            _keeper.forget()
        return got


@contextmanager
def engine(loaded: dict):
    """The held engine with `loaded` in it (only the change goes when it shares nodes with the scene held)."""
    global _engine
    from rostrum2d.engine import Engine
    with _lock:
        if _engine is None or _engine._stopped is not None:
            _engine = Engine()
        try:
            _engine.load(loaded)
        except Exception:
            _keeper.forget()                        # a refused scene: describe it whole next time
            raise
        yield _engine


def forget():
    """Inputs outside the document changed (a 3D render finished): the next look describes and sends everything."""
    with _lock:
        _keeper.forget()


@atexit.register
def close():
    global _engine
    with _lock:
        if _engine is not None:
            _engine.close()
            _engine = None
