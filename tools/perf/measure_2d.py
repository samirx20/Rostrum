"""How fast Rostrum2D's real window answers, drawn offscreen (S59). Times with perf_counter until the result is on
screen: the engine's frame has landed (bridge.frame moved on, the frame worker idle) and the window has drawn it.

    python tools/perf/measure_2d.py run [N]        # start split, open, drag, scrub, select, number field: median / worst
    python tools/perf/measure_2d.py start          # (child of `run`: one cold start, prints its split as JSON)
    python tools/perf/measure_2d.py soak SECONDS   # the interactions in a loop; RSS every 30 s (memory growth)
"""
import json
import os
import statistics
import subprocess
import sys
import time
T0 = time.perf_counter()
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "apps/2d/screen")]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
import checkout_paths  # noqa: E402

checkout_paths.use_this_checkout()


def rss_mb() -> float:
    """This process's working set (Windows API; no psutil in the environment)."""
    import ctypes
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (n, ctypes.c_size_t) for n in ("Peak", "WorkingSetSize", "QPPeak", "QPPaged", "QPNPPeak", "QPNP",
                                           "Pagefile", "PeakPagefile")]
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = wintypes.HANDLE          # a 64-bit handle (the default int cut it: 0 MB read)
    k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    if not k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
        raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
    return c.WorkingSetSize / 2**20


class Rig:
    """The real Session and window on the built-in sample, with waits that end when the result is on screen."""

    def __init__(self):
        from rostrum_gui.app import qt_app
        self.app = qt_app()
        from rostrum_core import Document
        from rostrum2d import KIND, run_source
        from screen2d.sample import SOURCE
        from screen2d.session import Session
        self.split = {"imports": time.perf_counter() - T0}
        self.session = Session((1600, 960))
        doc = Document.new(KIND)
        doc.run_script("sample.py", run_source(SOURCE, "sample.py"))
        t = time.perf_counter()
        self.session.files.put(doc)
        self.split["qml"] = time.perf_counter() - t
        t = time.perf_counter()
        self.landed(0)
        self.split["first frame"] = time.perf_counter() - t

    def events(self):
        """Events as the app's own loop runs them, deferred deletes included: processEvents outside app.exec() never
        frees a deleteLater'd object (old panel rows), which read as a leak of 70 MB/s that the real app doesn't have."""
        from PySide6.QtCore import QCoreApplication, QEvent
        self.app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    @property
    def b(self):
        return self.session.bridge

    def landed(self, before: int, limit: float = 20.0):
        """Events until a frame newer than `before` is in and the worker idle, then the window draws it."""
        end = time.perf_counter() + limit
        while not (self.b.frame > before and self.b.frames.idle()):
            self.events()
            if time.perf_counter() > end:
                raise RuntimeError(f"no frame after {limit} s (frame {self.b.frame}, asked after {before})")
            time.sleep(0.0005)
        self.events()
        self.session.win.grabWindow()            # the window draws the new state (bindings, delegates, picture)

    def timed(self, act) -> float:
        before = self.b.frame
        t = time.perf_counter()
        act()
        self.landed(before)
        return (time.perf_counter() - t) * 1000

    def drawn(self, act) -> float:
        """A change that may draw no new frame (a selection): its work plus the window's draw."""
        t = time.perf_counter()
        act()
        self.events()
        self.session.win.grabWindow()
        return (time.perf_counter() - t) * 1000

    # ---- the interactions --------------------------------------------------------------------------------------
    def drag(self, n):
        b = self.b
        b.select("card")
        assert b.beginMove(), "the drag did not start"
        out = [self.timed(lambda i=i: b.moveBy(3.0 * (i + 1), 2.0 * (i + 1))) for i in range(n)]
        self.timed(b.endDrag)
        b.undo()
        return out

    def scrub(self, n):
        return [self.timed(lambda i=i: self.b.setTime((i % 100) / 30)) for i in range(n)]

    def select(self, n):
        ids = ["card", "title", "dot", "rule", "lockup"]
        return [self.drawn(lambda i=i: self.b.select(ids[i % len(ids)])) for i in range(n)]

    def number(self, n):
        self.b.select("card")
        self.b.setTime(2.0)
        out = [self.timed(lambda i=i: self.b.setValue("radius", 20 + i % 30)) for i in range(n)]
        return out

    def open(self, n):
        from rostrum_core import Document
        from rostrum2d import KIND, run_source
        from screen2d.sample import SOURCE
        out = []
        for _ in range(n):
            doc = Document.new(KIND)
            doc.run_script("sample.py", run_source(SOURCE, "sample.py"))
            t = time.perf_counter()
            self.session.files.put(doc)
            self.landed(0)
            out.append((time.perf_counter() - t) * 1000)
        return out

    def close(self):
        self.session.close()


def stats(ms):
    return {"median": round(statistics.median(ms), 1), "worst": round(max(ms), 1), "n": len(ms)}


def profile(rig, name, n):
    import cProfile
    import pstats
    p = cProfile.Profile()
    p.enable()
    getattr(rig, name)(n)
    p.disable()
    pstats.Stats(p, stream=sys.stderr).sort_stats("cumulative").print_stats(25)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "start":
        rig = Rig()
        print(json.dumps({k: round(v * 1000, 1) for k, v in rig.split.items()}))
        rig.close()
        return
    if mode == "start-many":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        res = []
        for _ in range(n):
            t = time.perf_counter()
            out = subprocess.run([sys.executable, __file__, "start"], capture_output=True, text=True, check=True)
            split = json.loads(out.stdout.strip().splitlines()[-1])
            split["process"] = round((time.perf_counter() - t) * 1000, 1)
            res.append(split)
        print(json.dumps({k: stats([r[k] for r in res]) for k in res[0]}, indent=1))
        return
    rig = Rig()
    if mode == "profile":
        profile(rig, sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 20)
    elif mode == "run":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        out = {k: stats(getattr(rig, k)(n)) for k in ("drag", "scrub", "select", "number")}
        out["open"] = stats(rig.open(max(n // 4, 3)))
        print(json.dumps(out, indent=1))
    elif mode == "leak":                          # which interaction grows memory: each alone for a while
        for k in sys.argv[2:] or ("drag", "scrub", "select", "number"):
            before, t0 = rss_mb(), time.perf_counter()
            while time.perf_counter() - t0 < 15:
                getattr(rig, k)(10)
            print(f"{k}: {before:.0f} -> {rss_mb():.0f} MB in 15 s", flush=True)
    elif mode == "soak":
        secs, t0, last = float(sys.argv[2]), time.perf_counter(), 0.0
        print(f"rss 0 s: {rss_mb():.0f} MB", flush=True)
        while time.perf_counter() - t0 < secs:
            for k in ("drag", "scrub", "select", "number"):
                getattr(rig, k)(10)
            if time.perf_counter() - last > 30:
                last = time.perf_counter()
                print(f"rss {last - t0:.0f} s: {rss_mb():.0f} MB", flush=True)
        print(f"rss end: {rss_mb():.0f} MB", flush=True)
    rig.close()


if __name__ == "__main__":
    main()
