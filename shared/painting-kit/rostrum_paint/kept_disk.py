"""Kept layer states on disk: a paint layer's pixels after its first i strokes (canvas.py's chain key), in the shared
cache (kind "paint"), so a new process goes on from the nearest one instead of stamping every stroke before it.

A Drawn so far picture is the drawing with its first k strokes. In a fresh session (the finished picture read from its
PNG) that meant stamping every stroke up to k, and every whole layer under it: 1-10 s for a look at a moment of a
washed painting being painted on. Now a replay that stamps for long leaves a state about every `EVERY` s of stamping
and at each layer's end, written on a thread of its own; `_layer` reads the nearest one back.

A state is its exact float pixels (the bytes the replay had: going on from it stamps the same pixels as going on in
memory), only the box where anything is set (`_box`; outside it the layer is 0, `top` -1), squeezed with zlib (a
layer of a few washes over a big canvas is mostly nothing; a dense one is kept as it is, `PACK`).
"""
from __future__ import annotations

import atexit
import json
import queue
import threading
import zlib

import numpy as np

from rostrum_core.cache import CACHE, ENTRY, cache_key

EVERY = 0.4                     # s of stamping between two states kept on disk (a wash stroke is ~0.2-0.5 s)
PACK = 0.4                      # squeezed only when that makes it this much of its size or less
VERSION = "rostrum-paint-state@1"
_Q: queue.Queue = queue.Queue()
_LOCK = threading.Lock()
_thread: threading.Thread | None = None
_PENDING: set = set()          # states on the writer's queue
_MISSING: set = set()          # states looked for and not on disk: an export's every picture asks for the same ones


def _key(chain: str) -> str:
    return cache_key("paint.state", VERSION, [chain])


def _box(nonzero: np.ndarray) -> tuple[int, int, int, int] | None:
    rows, cols = np.flatnonzero(nonzero.any(axis=1)), np.flatnonzero(nonzero.any(axis=0))
    if not len(rows):
        return None
    return int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1


def has(chain: str) -> bool:
    """Whether the state is on disk (cheap: one file's presence, no use counted; a miss is remembered until this
    process keeps it)."""
    if chain in _MISSING:
        return False
    if (CACHE.path("paint", _key(chain)) / ENTRY).is_file():
        return True
    with _LOCK:
        if len(_MISSING) > 100_000:
            _MISSING.clear()
        _MISSING.add(chain)
    return False


def load(chain: str, w: int, h: int) -> tuple[np.ndarray, np.ndarray] | None:
    """(pixels HxWx4 float32, top HxW int32) of the state, or None when it is not on disk."""
    folder = CACHE.get("paint", _key(chain))
    if folder is None:
        return None
    meta = json.loads((folder / "state.json").read_text(encoding="utf-8"))
    if meta["w"] != w or meta["h"] != h:
        raise ValueError(f"paint state {chain[:12]}: kept at {meta['w']} x {meta['h']}, asked at {w} x {h}")
    px, top = np.zeros((h, w, 4), np.float32), np.full((h, w), -1, np.int32)
    for name, arr, dtype, depth in (("px", px, np.float32, (4,)), ("top", top, np.int32, ())):
        box = meta[name]
        if box is not None:
            y0, y1, x0, x1 = box
            raw = (folder / f"{name}.bin").read_bytes()
            raw = zlib.decompress(raw) if meta.get("packed", {}).get(name, True) else raw
            arr[y0:y1, x0:x1] = np.frombuffer(raw, dtype).reshape((y1 - y0, x1 - x0, *depth))
    return px, top


def save(chain: str, px: np.ndarray, top: np.ndarray) -> None:
    """Keep the state on disk (its set boxes copied now, written on the writer thread: the replay goes on)."""
    with _LOCK:
        if chain in _PENDING:
            return
    if has(chain):
        return
    with _LOCK:
        _PENDING.add(chain)
    h, w = top.shape
    pbox = _box(px.view(np.uint32).any(axis=2))        # bits, not values: -0.0 comes back as -0.0
    tbox = _box(top >= 0)
    parts = {"px": (pbox, px[pbox[0]:pbox[1], pbox[2]:pbox[3]].copy() if pbox else None),
             "top": (tbox, top[tbox[0]:tbox[1], tbox[2]:tbox[3]].copy() if tbox else None)}
    _start()
    _Q.put((chain, w, h, parts))


def _write(chain: str, w: int, h: int, parts: dict) -> None:
    def make(tmp):
        packed = {}
        for name, (_, arr) in parts.items():
            if arr is not None:
                raw = np.ascontiguousarray(arr).tobytes()
                small = zlib.compress(raw, 1)
                packed[name] = len(small) < PACK * len(raw)     # a dense wash reads back faster unsqueezed
                (tmp / f"{name}.bin").write_bytes(small if packed[name] else raw)
        (tmp / "state.json").write_text(json.dumps({"w": w, "h": h, "packed": packed,
                                                    **{n: b for n, (b, _) in parts.items()}}), encoding="utf-8")
    try:
        CACHE.put("paint", _key(chain), make, {"w": w, "h": h, "chain": chain})
    finally:
        with _LOCK:
            _PENDING.discard(chain)
            _MISSING.discard(chain)


def _run() -> None:
    while True:
        job = _Q.get()
        try:
            _write(*job)
        except Exception as e:   # noqa: BLE001  (a state not kept only costs a replay later; said, never fatal)
            print(f"rostrum_paint: a paint state was not kept on disk: {e}", flush=True)
        finally:
            _Q.task_done()


def _start() -> None:
    global _thread
    with _LOCK:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_run, name="paint-states", daemon=True)
            _thread.start()


def flush() -> None:
    """Wait until every state asked for is written."""
    if _thread is not None and _thread.is_alive():
        _Q.join()


atexit.register(flush)
