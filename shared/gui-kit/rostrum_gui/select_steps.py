"""`selecttime <id> <id> … [n] [profile]` (any app, through layout_run.kit_step): what switching the selection costs the
screen thread.

Selects each id in turn (n rounds, default 6; a number is n); per switch, the screen thread's busy ms from the select
until it is idle again (the select slot, the events it queues, the picture or sound arriving), its own processor time
(other programs' share left out) and its longest stretch without a wait (what a pointer event waits for). The first
round is a warm-up, printed apart (the first pick of a kind). Prints median and worst, then clears the selection.
`profile`: the 40 most costly functions of the counted switches (cProfile; ROSTRUM_PROFILE_SORT=tottime sorts by own
time, ROSTRUM_PROFILE_CALLERS=<names> lists who called them). `cost(acts, n)` measures any other action this way
(2D's `opentime`).
"""
from __future__ import annotations

import os
import statistics
import time

from PySide6.QtCore import QAbstractEventDispatcher, QCoreApplication, QEventLoop, QTimer

IDLE_MS = 150


class _Cpu:
    """The screen thread's own processor time in ms (Windows: its cycle count, at the rate a short spin measures;
    elsewhere thread_time): unlike the busy ms it leaves out the time other programs took the processor, so a
    loaded machine still gives the switch's own cost."""

    def __init__(self):
        self._q = None
        if os.name == "nt":
            import ctypes
            k = ctypes.windll.kernel32
            k.GetCurrentThread.restype = ctypes.c_void_p
            n, h = ctypes.c_uint64(), k.GetCurrentThread()

            def cycles():
                k.QueryThreadCycleTime(ctypes.c_void_p(h), ctypes.byref(n))
                return n.value
            self._q, rates = cycles, []
            for _ in range(5):                       # the fastest of five 20 ms spins: a spin cut short by another
                c0, t0 = cycles(), time.perf_counter()   # program reads slower, never faster
                while time.perf_counter() - t0 < 0.02:
                    pass
                rates.append((cycles() - c0) / (time.perf_counter() - t0))
            self._rate = max(rates) / 1000

    def now(self) -> float:
        return self._q() / self._rate if self._q else time.thread_time() * 1000


def _wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


class _Busy:
    """Busy ms of the screen thread: from each wake-up of its event loop to its next wait."""

    def __init__(self):
        self._d = QAbstractEventDispatcher.instance()
        self.total, self._up, self.longest = 0.0, time.perf_counter(), 0.0
        self._d.awake.connect(self._awake)
        self._d.aboutToBlock.connect(self._block)

    def _awake(self):
        if self._up is None:
            self._up = time.perf_counter()

    def _block(self):
        if self._up is not None:
            run = time.perf_counter() - self._up
            self.total += run
            self.longest = max(self.longest, run)
            self._up = None

    def stretch(self) -> float:
        """The longest stretch without a wait since the last call, in ms: what holds up a pointer event (a press or
        a move waits at most this long), and the frame a person sees late."""
        out, self.longest = self.longest * 1000, 0.0
        return out

    def now(self) -> float:
        return (self.total + (time.perf_counter() - self._up if self._up is not None else 0.0)) * 1000

    def close(self):
        self._d.awake.disconnect(self._awake)
        self._d.aboutToBlock.disconnect(self._block)


def cost(acts: list, n: int, profile: bool = False) -> dict:
    """Run each (label, fn) of `acts` in turn, n counted rounds after a warm-up round, each on an idle screen thread;
    per label: {"ms": busy, "cpu": its own processor time, "held": the longest stretch without a wait, "first": the
    warm-up's busy}. `profile`: a cProfile of the counted rounds (of the warm-up when n is 0), under "profile"."""
    prof = None
    if profile:
        import cProfile
        prof = cProfile.Profile()
    from . import after_frame
    out = {label: {"ms": [], "cpu": [], "held": [], "first": [], "own": []} for label, _ in acts}
    _wait(300)
    busy, clock, mark = _Busy(), _Cpu(), [None]

    def heard():                                         # the part put off to the frame after starts: what came before
        if mark[0] is None:                              # it is the action's own frame
            mark[0] = busy.now()
    after_frame.HEARD.append(heard)
    try:
        for r in range(n + 1):
            for label, fn in acts:
                _wait(IDLE_MS)
                b0, c0, _ = busy.now(), clock.now(), busy.stretch()
                mark[0] = None
                if prof and (r or not n):
                    prof.enable()
                fn()
                QCoreApplication.processEvents()
                _wait(IDLE_MS)
                if prof and (r or not n):
                    prof.disable()
                got = out[label]
                if r:
                    got["ms"].append(busy.now() - b0)
                    got["cpu"].append(clock.now() - c0)
                    got["held"].append(busy.stretch())
                    got["own"].append((mark[0] if mark[0] is not None else busy.now()) - b0)
                else:
                    got["first"].append(busy.now() - b0)
    finally:
        after_frame.HEARD.remove(heard)
        busy.close()
    if prof:
        out["profile"] = prof
    return out


def said(name: str, got: dict) -> str:
    """One label's line: busy, own processor time and longest stretch (median, worst), and the warm-up's."""
    ms, cpu, held = got["ms"], got["cpu"], got["held"]
    m = statistics.median
    first = " ".join(f"{v:.0f}" for v in got["first"])
    if not ms:
        return f"{name}: first round only: {first} ms"
    return (f"{name}: {len(ms)} times; screen thread median {m(ms):.1f}, worst {max(ms):.1f} ms; its own processor time "
            f"median {m(cpu):.1f}, worst {max(cpu):.1f} ms; longest stretch without a wait median {m(held):.1f}, "
            f"worst {max(held):.1f} ms; first round {first} ms"
            + (f"; before the part put off to the next frame median {m(got['own']):.1f}, worst {max(got['own']):.1f} ms"
               if got.get("own") and got["own"] != ms else ""))


def print_profile(prof) -> None:
    import io
    import pstats
    out = io.StringIO()
    st = pstats.Stats(prof, stream=out).sort_stats(os.environ.get("ROSTRUM_PROFILE_SORT", "cumulative"))
    st.print_stats(40)
    for f in filter(None, os.environ.get("ROSTRUM_PROFILE_CALLERS", "").split(",")):
        st.print_callers(f)
    print(out.getvalue())


def clicks(win, args: list[str]) -> None:
    """`clicktime <x>,<y> … [n] [profile]`: real left clicks (press, release: QTest, the mouse's own path) at those
    window points in turn, each measured as a selection switch is (a layer row, a layer on the canvas), and apart the
    busy ms before the part a pick puts off to the frame after (after_frame.py): the click's own frame."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    pts = [a for a in args if "," in a]
    if not pts:
        raise ValueError("clicktime <x>,<y> <x>,<y> … [n] [profile]")
    n = int(next((a for a in args if a.isdigit()), 6))

    def click(p):
        at = QPoint(*(int(float(v)) for v in p.split(",")))
        QTest.mouseMove(win, at)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
    got = cost([(p, lambda p=p: click(p)) for p in pts], n, "profile" in args)
    every = {k: [v for p in pts for v in got[p][k]] for k in ("ms", "cpu", "held", "first", "own")}
    print(said(f"clicktime {' '.join(pts)}", every).replace(" times;", " clicks;"))
    print("  each point (busy / its own frame, median-worst): " + "; ".join(
        f"{p} {statistics.median(got[p]['ms']):.0f}-{max(got[p]['ms']):.0f} / {statistics.median(got[p]['own']):.0f}-{max(got[p]['own']):.0f}"
        for p in pts if got[p]["ms"]))
    if "profile" in got:
        print_profile(got["profile"])


def do(bridge, args: list[str]) -> None:
    ids = [a for a in args if not a.isdigit() and a != "profile"]
    if not ids:
        raise ValueError("selecttime <id> <id> … [n] [profile]")
    n = int(next((a for a in args if a.isdigit()), 6))
    got = cost([(i, lambda i=i: bridge.select(i)) for i in ids], n, "profile" in args)
    bridge.select("")
    every = {k: [v for i in ids for v in got[i][k]] for k in ("ms", "cpu", "held")}
    every["first"] = [v for i in ids for v in got[i]["first"]]
    print(said(f"selecttime {' '.join(ids)}", every).replace(" times;", " switches;"))
    print("  each: " + " ".join(f"{v:.0f}" for r in range(n) for v in (got[i]["ms"][r] for i in ids)))
    if "profile" in got:
        print_profile(got["profile"])
