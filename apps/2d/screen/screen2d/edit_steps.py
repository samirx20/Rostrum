"""`edittime`: what one edit costs, per edit kind, through the same bridge slots a click, a typed field, a drag or a key uses.

    edittime field|dragend|key|pin|undo [n]
        n repetitions (default 20), each a real change (alternating), on the layer "card" (any document with it):
        field: its x typed in the inspector | dragend: a canvas drag, only the release timed | key: a key at the playhead
        (the key mark's toggle) added, then removed next round | pin: Pin to frame / Unpin from frame | undo: one undo of
        an edit made just before (only the undo timed).
        Per repetition: the screen thread's busy ms until it is idle again, and the ms until the picture asked after the
        change arrived; the stages (describe, load, pixels, engine split) are each repetition's sum. Medians and worst
        on one line. Everything done is undone after.
"""
from __future__ import annotations

import statistics
import time

from PySide6.QtCore import QCoreApplication

from .drag_steps import Busy, _wait
from .playstats import STATS

WORDS = ("edittime",)
KINDS = ("field", "dragend", "key", "pin", "undo")
IDLE_MS, LIMIT_S = 100, 10.0


class _Pictures:
    """The bridge's frame requests and arrivals, to tell the picture asked after a change from one asked before."""

    def __init__(self, bridge):
        self.frames, self.real = bridge.frames, bridge.frames.request
        self.first_ask = self.last_ready = None
        self.armed = False
        self.frames.request = self._asked
        self.frames.ready.connect(self._ready)

    def _asked(self, *a, **kw):
        if self.armed and self.first_ask is None:
            self.first_ask = time.perf_counter()
        return self.real(*a, **kw)

    def _ready(self, *_):
        if self.first_ask is not None:
            self.last_ready = time.perf_counter()

    def arm(self):
        self.first_ask = self.last_ready = None
        self.armed = True

    def close(self):
        self.frames.request = self.real
        self.frames.ready.disconnect(self._ready)


def _settle(pics, what):
    """Until a picture asked after the change arrived and the screen has been quiet for IDLE_MS; fails if none in 10 s."""
    end = time.perf_counter() + LIMIT_S
    while pics.last_ready is None:
        if time.perf_counter() > end:
            raise RuntimeError(f"edittime {what}: no picture arrived within {LIMIT_S:.0f} s of the change")
        _wait(5)
    while True:
        seen = pics.last_ready
        _wait(IDLE_MS)
        if pics.last_ready == seen:
            return


def _kind(bridge, kind):
    """(setup before the timed part or None, the timed action i -> None, how many undo steps one repetition leaves)."""
    if kind in ("field", "undo"):
        def act(i):
            bridge.setValue("x", 760 + 40 * (i % 2 + 1))
        return (act if kind == "undo" else None), ((lambda i: bridge.undo()) if kind == "undo" else act), (0 if kind == "undo" else 1)
    if kind == "key":
        return None, lambda i: bridge.toggleAnimate("x"), 1
    if kind == "pin":
        def pin(i):
            if not bridge.run("layer:pin" if i % 2 == 0 else "layer:unpin"):
                raise RuntimeError(f"edittime pin: not available ({bridge.status})")
        return None, pin, 1
    if kind == "dragend":
        def begin(i):
            if not bridge.beginMove():
                raise RuntimeError("edittime dragend: nothing to move")
            for f in (0.25, 0.5, 0.75, 1.0):
                bridge.moveBy(60 * f * (1 if i % 2 == 0 else -1), 30 * f)
        return begin, lambda i: bridge.endDrag(), 1
    raise ValueError(f"edittime: no kind {kind!r} ({' | '.join(KINDS)})")


def _med(v):
    return f"{statistics.median(v):.1f}" if v else "-"


def _spread(v):
    return f"median {_med(v)} worst {max(v):.1f}"


def edit_time(bridge, kind, n=20):
    setup, action, undos = _kind(bridge, kind)
    bridge.select("card")
    start = repr(bridge.placed_item("card"))
    _wait(300)
    STATS.on = True
    pics, busy = _Pictures(bridge), Busy()
    gui, pic, stages, done = [], [], {}, 0
    try:
        for i in range(n):
            if setup:
                setup(i)
                _wait(400)                       # the setup's own pictures arrive first
            _wait(IDLE_MS)
            STATS.reset()
            pics.arm()
            b0, t0 = busy.now(), time.perf_counter()
            action(i)
            QCoreApplication.processEvents()
            _settle(pics, kind)
            gui.append(busy.now() - b0)
            pic.append((pics.last_ready - t0) * 1000)
            for k, v in STATS.ms.items():
                stages.setdefault(k, []).append(sum(v))
            if kind != "undo":
                done += undos
            pics.armed = False
        for _ in range(done):                    # the document as it was
            bridge.undo()
            _wait(IDLE_MS)
    finally:
        pics.close()
        busy.close()
        STATS.on = STATS.log
    if repr(bridge.placed_item("card")) != start:
        raise RuntimeError(f"edittime {kind}: the document did not come back as it started")
    eng = " ".join(f"{k[4:]} {_med(v)}" for k, v in stages.items() if k.startswith("eng."))
    rest = " ".join(f"{k} {_med(v)}" for k, v in stages.items() if not k.startswith("eng.") and k not in ("describe", "load", "pixels"))
    print(f"edittime {kind}: n={n}; gui {_spread(gui)} ms; picture {_spread(pic)} ms; describe {_med(stages.get('describe', []))}; "
          f"load {_med(stages.get('load', []))}; pixels {_med(stages.get('pixels', []))}" + (f"; eng {eng}" if eng else "")
          + (f"\n  stages: {rest}" if rest else ""))


def do_edit_step(bridge, word, rest, step):
    if not rest:
        raise ValueError(f"step {step!r}: edittime {' | '.join(KINDS)} [n]")
    edit_time(bridge, rest[0], int(rest[1]) if rest[1:] else 20)
