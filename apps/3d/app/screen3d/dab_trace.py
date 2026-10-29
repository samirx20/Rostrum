"""Where a clay dab's time goes, hop by hop (CL2b; tools/clay_hops.py reads it). Off unless `start()` was called:
then every live dab request is one record (ms on one clock, time.perf_counter):
  tMove   the first pointer move the request carries (Python, GUI thread)
  tSend   the request handed to the engine thread       tJob    the engine thread starts it
  tEng0/1 around the engine request (its reply: dabMs, drawMs, totalMs, perf: Storm's counters)
  tAsked / tDab0 / tDab1 (the window's view) when the clay work was asked for early (absent: it ran in the request), began, ended
  tCopy0/1 the picture copied out of shared memory       serial  the picture's number
  tReady  the GUI thread told the picture is in          tSwap   the window's first frame shown after that
In the window's own view (view_item.py) there is no picture copy: tRender0/1 are the render thread's dab + draw and
`frame` the frame that drew it; tSwap is when that frame's swap returned.
and Python's garbage collections (start, ms, generation)."""
from __future__ import annotations

import gc
import time

RECORDS: list[dict] | None = None
GCS: list[dict] = []
_gc_t0 = [0.0]


def now() -> float:
    return time.perf_counter() * 1000


def on() -> bool:
    return RECORDS is not None


def start():
    global RECORDS
    RECORDS = []
    GCS.clear()
    if _gc_hook not in gc.callbacks:
        gc.callbacks.append(_gc_hook)


def stop():
    global RECORDS
    if _gc_hook in gc.callbacks:
        gc.callbacks.remove(_gc_hook)
    out, RECORDS = RECORDS, None
    return out


def _gc_hook(phase, info):
    if phase == "start":
        _gc_t0[0] = now()
    else:
        GCS.append({"t": _gc_t0[0], "ms": now() - _gc_t0[0], "gen": info.get("generation")})


def ready(serial: int):
    if RECORDS is not None:
        for r in reversed(RECORDS):
            if r.get("serial") == serial and "tReady" not in r:
                r["tReady"] = now()
                return


def shown(frame: int, t_ms: float):
    """The window's own view: its frame `frame` is on screen since t_ms (view_item.ViewLink.shown)."""
    if RECORDS is not None:
        for r in reversed(RECORDS):
            if r.get("frame") is not None and "tSwap" not in r and r["frame"] <= frame:
                r["tSwap"] = t_ms


def swapped(serial: int):
    """A frame was shown with picture `serial` (or newer) on screen."""
    if RECORDS is not None:
        t = now()
        for r in reversed(RECORDS):
            if "tReady" in r and "tSwap" not in r and r["serial"] <= serial:
                r["tSwap"] = t
