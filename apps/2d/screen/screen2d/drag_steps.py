"""`dragtime`: what one pointer move of a drag costs the screen's thread, per drag kind, through the same slots the
timeline and the canvas call (so a check measures exactly what a person's drag does).

    dragtime bar|trim|key|layer|frame|scrub [n] [profile]
        n pointer moves of that drag (default 60), one per screen refresh (16 ms apart, as a hand gives them): each
        move's time on the screen's thread (the slot, then everything it set off: rows, panels, bindings, a picture
        arriving), median and worst; how many pictures the engine was asked for and drew. `profile`: the 25 most
        costly functions of the moves (cProfile, cumulative) after the line.

bar: the "card" bar moved 2 s later (a frame per move); trim: its end trimmed; key: title's last y key; layer: "card" on the canvas;
frame: the frame on the canvas (the sample's layers; any document with those names); scrub: the playhead dragged from
0.2 s over 3 s (a new frame per move, nothing changed). Each drag is undone after.
"""
from __future__ import annotations

import gc
import os
import statistics
import time

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from rostrum_core.keys import keys_of

from .playstats import STATS

WORDS = ("dragtime",)
PACE_MS = 16


def _key_of(bridge, layer="title", prop="y"):
    return keys_of(bridge.placed_item(layer), prop)[-1]


def _drag(bridge, kind):
    """(begin, move to fraction f, end) of one drag of `kind`."""
    if kind in ("bar", "trim"):
        part = "move" if kind == "bar" else "end"
        t0 = 0.5 if part == "move" else bridge.comp()["duration"]
        return (lambda: bridge.beginBarDrag("card", part, t0),
                lambda f: bridge.barDragTo(t0 + (2.0 if part == "move" else -2.0) * f, 0.1), bridge.endDrag)
    if kind == "key":
        key = _key_of(bridge)
        return (lambda: bridge.beginKeyDrag(key["id"]), lambda f: bridge.keyDragTo(key["t"] + 2.0 * f, 0.1), bridge.endDrag)
    if kind == "layer":
        return (lambda: (bridge.select("card"), bridge.beginMove())[1], lambda f: bridge.moveBy(300 * f, 120 * f), bridge.endDrag)
    if kind == "frame":
        from .frame_view import box_at
        b = box_at(bridge.placed(), bridge._t)
        fd = bridge.frameDrag
        return (lambda: (fd.pick(), fd.begin("move", b["cx"], b["cy"], 0))[1], lambda f: fd.moveBy(400 * f, 0), fd.end)
    if kind == "scrub":
        return (lambda: True), (lambda f: bridge.setTime(0.2 + 3.0 * f)), (lambda: None)
    raise ValueError(f"dragtime: no drag kind {kind!r} (bar | trim | key | layer | frame | scrub)")


def _wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(max(int(ms), 0), loop.quit)
    loop.exec()


def _spread(ms) -> str:
    q = sorted(ms)
    return f"median {statistics.median(q):.1f}, worst {q[-1]:.1f} ms" if q else "none"


class Busy:
    """The screen thread's busy time: from each wake-up of its event loop to its next wait (Qt's event dispatcher), so
    work a drag puts off (a timer, a picture arriving, the window's polish) counts in the frame it lands in."""

    def __init__(self):
        from PySide6.QtCore import QAbstractEventDispatcher
        self._d = QAbstractEventDispatcher.instance()
        self.total, self._up = 0.0, time.perf_counter()
        self._d.awake.connect(self._awake)
        self._d.aboutToBlock.connect(self._block)

    def _awake(self):
        if self._up is None:
            self._up = time.perf_counter()

    def _block(self):
        if self._up is not None:
            self.total += time.perf_counter() - self._up
            self._up = None

    def now(self) -> float:
        """Busy ms so far (the stretch under way counted)."""
        return (self.total + (time.perf_counter() - self._up if self._up is not None else 0.0)) * 1000

    def close(self):
        self._d.awake.disconnect(self._awake)
        self._d.aboutToBlock.disconnect(self._block)


def drag_time(bridge, kind, n=60, profile=False):
    begin, move, end = _drag(bridge, kind)
    _wait(300)                                   # what opening set off settles first
    STATS.reset()
    STATS.on = True
    asked = [0]
    real = bridge.frames.request

    def counted(*a, **kw):
        asked[0] += 1
        return real(*a, **kw)
    bridge.frames.request = counted
    prof = None
    if profile:
        import cProfile
        prof = cProfile.Profile()
    busy = Busy()
    gc_at = [0.0]

    def collected(phase, info):                  # Python's cycle collector, timed (a pause shows as a slow move)
        if phase == "start":
            gc_at[0] = time.perf_counter()
        elif STATS.on:
            STATS.ms[f"gc{info['generation']}"].append((time.perf_counter() - gc_at[0]) * 1000)
    gc.callbacks.append(collected)
    try:
        if not begin():
            raise RuntimeError(f"dragtime {kind}: the drag didn't start: {bridge.status}")
        ms = []
        for i in range(1, n + 1):
            t0, b0 = time.perf_counter(), busy.now()
            if prof:
                prof.enable()
            move(i / n)
            QCoreApplication.processEvents()
            _wait(PACE_MS - (time.perf_counter() - t0) * 1000)      # the rest of this frame: what the move put off
            if prof:
                prof.disable()
            ms.append(busy.now() - b0)
        b0 = busy.now()
        end()
        _wait(PACE_MS)
        release = busy.now() - b0
        if kind != "scrub":
            bridge.undo()                        # the document as it was: each kind measured on the same scene
            _wait(PACE_MS)
    finally:
        gc.callbacks.remove(collected)
        busy.close()
        bridge.frames.request = real
        STATS.on = STATS.log
    drawn = len(STATS.ms.get("pixels", []))
    print(f"dragtime {kind}: {n} moves; screen thread busy per move {_spread(ms)}; release {release:.1f} ms; "
          f"pictures asked {asked[0]}, drawn {drawn} (engine {_spread(STATS.ms.get('pixels', []))})")
    if os.environ.get("ROSTRUM2D_DRAG_SERIES") == "1":
        print("  per move: " + " ".join(f"{m:.0f}" for m in ms))
    stages = {k: v for k, v in STATS.ms.items() if k not in ("pixels", "image", "load") and not k.startswith("eng.")}
    print("  stages: " + "; ".join(f"{k.replace(chr(0x2192), '-')} {_spread(v)} x{len(v)}" for k, v in stages.items()))
    if prof:
        import io
        import pstats
        out = io.StringIO()
        st = pstats.Stats(prof, stream=out).sort_stats(os.environ.get("ROSTRUM2D_DRAG_SORT", "cumulative")); st.print_stats(40); [st.print_callees(f) for f in os.environ.get("ROSTRUM2D_DRAG_CALLEES", "").split(",") if f]
        print(out.getvalue())


DETAIL = ("rostrum_core.run:plan_indexed", "screen2d.outline:rows", "rostrum2d.retime:timed",
          "screen2d.timeline_rows:TimelineRows._layers_check", "screen2d.timeline_rows:TimelineRows._push_rows",
          "rostrum_gui.bridge_select:SelectSlots._refresh", "screen2d.hooks:Hooks2D._rows", "rostrum_gui.model:RowsModel.update",
          "rostrum_gui.effects:EffectsPart._sync", "screen2d.painter:Painter._refresh",
          "screen2d.painter:Painter._doc_changed", "rostrum_gui.time_snap:TimeSnap.show", "screen2d.bridge2d:Bridge2D._outline_check",
          "screen2d.motion_path:MotionPath._changed")


def _detail():
    """`detail`: time these functions during the drag (each one's median and worst per call, as STATS stages)."""
    import functools
    import importlib
    undo = []
    for spec in DETAIL:
        mod, _, attr = spec.partition(":")
        try:
            owner = importlib.import_module(mod)
            *path, name = attr.split(".")
            for p in path:
                owner = getattr(owner, p)
            fn = getattr(owner, name)
        except (ImportError, AttributeError):
            continue

        def timed(*a, _fn=fn, _name=attr.split(".")[-1], **kw):
            t0 = time.perf_counter()
            try:
                return _fn(*a, **kw)
            finally:
                if STATS.on:
                    STATS.ms["fn." + _name].append((time.perf_counter() - t0) * 1000)
        setattr(owner, name, functools.wraps(fn)(timed))
        undo.append((owner, name, fn))
    return lambda: [setattr(o, n, f) for o, n, f in undo]


def do_drag_step(bridge, word, rest, step):
    if "detail" in rest:
        restore = _detail()
        try:
            return drag_time(bridge, rest[0], int(rest[1]) if rest[1:] and rest[1].isdigit() else 60, "profile" in rest)
        finally:
            restore()
    drag_time(bridge, rest[0], int(rest[1]) if rest[1:] and rest[1].isdigit() else 60, "profile" in rest)
