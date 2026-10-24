"""The problems list's looks, in a process of their own (problems.py). A look is pure Python over every layer (seen.py,
geometry, keys) for 100 ms and more on a busy scene; run on a thread of the screen's own interpreter it held Python's
lock, so the screen thread stalled on whatever the person did next (an undo on the busy scene: 90-175 ms). Here the
screen's worker thread only waits on a pipe. The process keeps its own engine and scene keeper; it is started on the
first look and ended with the screen (`close`); if it dies, the next look starts a new one.
"""
from __future__ import annotations

import multiprocessing


def _same(old, new):
    """`new` with every part equal to `old`'s part at the same place (items matched by id) being that very object of
    `old`: a document comes through the pipe as a fresh copy, and the scene keeper (scene_keep.py) knows unchanged parts
    by identity, so the engine is sent only the change."""
    if old is None or new == old:
        return old if new == old else new
    if isinstance(new, dict) and isinstance(old, dict):
        return {k: _same(old.get(k), v) for k, v in new.items()}
    if isinstance(new, list) and isinstance(old, list):
        by = {o["id"]: o for o in old if isinstance(o, dict) and "id" in o}
        return [_same(by.get(v["id"]) if isinstance(v, dict) and "id" in v else (old[i] if i < len(old) else None), v)
                for i, v in enumerate(new)]
    return new


def _serve(conn):
    from rostrum2d import textsize
    from rostrum2d.diagnose_engine import everything
    from rostrum2d.engine import Engine
    from rostrum2d.scene_keep import Keeper
    eng, keeper, last = Engine(), Keeper(), None     # its engine is sent only what changed (scene_keep.py)
    try:
        while (job := conn.recv()) is not None:
            try:
                last = _same(last, job[0])
                with textsize.use(eng):    # texts measured with its own engine
                    conn.send(("ok", everything(last, *job[1:], eng, keeper)))
            except Exception as e:  # noqa: BLE001  handed back, raised there
                conn.send(("error", f"{type(e).__name__}: {e}"))
    finally:
        eng.close()


class Looker:
    """The process, from the screen's side: `everything(data, comp_id, folder, markers)` is diagnose_engine.everything."""

    def __init__(self):
        self._proc = None

    def _start(self):
        ctx = multiprocessing.get_context("spawn")
        self._conn, child = ctx.Pipe()
        self._proc = ctx.Process(target=_serve, args=(child,), name="problems2d", daemon=True)
        self._proc.start()
        child.close()

    def everything(self, data, comp_id, folder, markers) -> list[dict]:
        if self._proc is None or not self._proc.is_alive():
            self._start()
        try:
            self._conn.send((data, comp_id, folder, markers))
            kind, value = self._conn.recv()
        except (EOFError, OSError) as e:
            self._proc = None
            raise RuntimeError(f"the problems look's process ended ({e or 'no answer'}); the next change looks again") from e
        if kind == "error":
            raise RuntimeError(value)
        return value

    def close(self):
        if self._proc is None:
            return
        try:
            self._conn.send(None)
        except OSError:
            pass
        self._proc.join(10)
        if self._proc.is_alive():
            self._proc.terminate()             # our own child, by its handle
        self._proc = None
