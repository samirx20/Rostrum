"""On-screen FPS readout, process memory, and the `--measure` / `--screenshot` drivers."""
import ctypes
import json
import time
from ctypes import wintypes

from PySide6.QtCore import QObject, Property, QTimer, Qt, Signal


class _PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                       "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                                       "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]


_k32, _psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
_k32.GetCurrentProcess.restype = wintypes.HANDLE
_psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]


def memory_mb():
    """Working set and private bytes of this process, in MB (Windows; psapi via ctypes, no extra package)."""
    pmc = _PMC(); pmc.cb = ctypes.sizeof(pmc)
    ok = _psapi.GetProcessMemoryInfo(_k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    if not ok:
        raise OSError("GetProcessMemoryInfo failed")
    return {"working_set": pmc.WorkingSetSize / 2**20, "private": pmc.PrivateUsage / 2**20}


class Stats(QObject):
    """Counts window frames (frameSwapped, render thread) and decoded video frames; QML reads the rates."""
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.swaps, self.video_frames = [], 0
        self._win_fps = self._vid_fps = self._mem = 0.0
        self._last = (time.perf_counter(), 0, 0)

    def attach(self, window):
        window.frameSwapped.connect(self._on_swap, Qt.DirectConnection)
        t = QTimer(self); t.timeout.connect(self._tick); t.start(500)

    def _on_swap(self):
        self.swaps.append(time.perf_counter())

    def on_video_frame(self, *_):
        self.video_frames += 1

    def _tick(self):
        now, n0, v0 = self._last
        t, n, v = time.perf_counter(), len(self.swaps), self.video_frames
        self._win_fps, self._vid_fps = (n - n0) / (t - now), (v - v0) / (t - now)
        self._mem = memory_mb()["working_set"]
        self._last = (t, n, v)
        self.changed.emit()

    windowFps = Property(float, lambda s: s._win_fps, notify=changed)
    videoFps = Property(float, lambda s: s._vid_fps, notify=changed)
    memoryMb = Property(float, lambda s: s._mem, notify=changed)


def _pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else None


class Measurer(QObject):
    """Warm up 1.5 s, then record frame times + memory for `seconds`, optionally clicking around and resizing."""
    SIZES = [(1600, 960), (1280, 800), (1920, 1080), (1440, 900)]

    def __init__(self, app, window, root, stats, viewport, args):
        super().__init__()
        self.app, self.win, self.root, self.stats, self.vp, self.args = app, window, root, stats, viewport, args
        self.events, self.mem = [], []
        root.setProperty("viewMode", args.mode)
        root.setProperty("playing", True)
        QTimer.singleShot(1500, self._start)

    def _start(self):
        self.t0, self.i0, self.v0 = time.perf_counter(), len(self.stats.swaps), self.stats.video_frames
        self.mem.append(memory_mb())
        self.timer = QTimer(self); self.timer.timeout.connect(self._step); self.timer.start(250)
        QTimer.singleShot(int(self.args.measure * 1000), self._finish)

    def _step(self):
        self.mem.append(memory_mb())
        if not self.args.churn:
            return
        k = len(self.mem)
        self.root.setProperty("selectedIndex", k % 6)  # "click" a new project item every 250 ms
        self.events.append(("select", k % 6))
        if hasattr(self.vp, "_op"):  # Hydra viewport: drag-orbit and click-pick through the same camera operations
            self.vp._op("orbit", 12.0, 3.0 if k % 2 else -3.0)
            if k % 4 == 0:
                dpr = self.win.devicePixelRatio()
                self.vp._op("pick", self.vp.width() * 0.6 * dpr, self.vp.height() * 0.5 * dpr)
            self.events.append(("orbit+pick", self.vp.property("picked")))
        if k % 6 == 0:  # resize every 1.5 s
            w, h = self.SIZES[(k // 6) % len(self.SIZES)]
            self.win.resize(w, h); self.events.append(("resize", f"{w}x{h}"))

    def _finish(self):
        self.timer.stop()
        t1 = time.perf_counter()
        swaps = [t for t in self.stats.swaps[self.i0:] if t <= t1]
        gaps = [(b - a) * 1000 for a, b in zip(swaps, swaps[1:])]
        vids = self.stats.video_frames - self.v0
        dur = t1 - self.t0
        out = {
            "mode": self.args.mode, "seconds": round(dur, 3), "churn": self.args.churn,
            "window_frames": len(swaps), "window_fps": round(len(swaps) / dur, 2),
            "frame_ms": {k: round(v, 2) for k, v in (("p50", _pct(gaps, 50)), ("p95", _pct(gaps, 95)),
                                                     ("p99", _pct(gaps, 99)), ("max", max(gaps or [0])))
                         if v is not None},
            "frames_over_33ms": sum(g > 33.4 for g in gaps), "frames_over_50ms": sum(g > 50 for g in gaps),
            "video_frames": vids, "video_fps": round(vids / dur, 2),
            "memory_mb": {"start_ws": round(self.mem[0]["working_set"], 1),
                          "peak_ws": round(max(m["working_set"] for m in self.mem), 1),
                          "end_ws": round(self.mem[-1]["working_set"], 1),
                          "end_private": round(self.mem[-1]["private"], 1)},
            "events": len(self.events),
            "picked": sorted({str(e[1]) for e in self.events if e[0] == "orbit+pick" and e[1]}), "final_size": [self.win.width(), self.win.height()],
            "gl": getattr(self.vp, "glInfo", {}) if self.vp is not None else {},
        }
        with open(self.args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(json.dumps(out, indent=2))
        self.app.exit(0 if swaps else 2)  # no frames at all = fail loudly


def screenshot_later(app, window, path, threaded, delay_ms=2000):
    """One-thread loop: grabWindow() (whole window, popups included). Threaded loop: QML's async grabToImage
    (Main.qml shoot(); panels only), because grabWindow() from Python there deadlocks (README › Threading)."""
    def grab():
        img = window.grabWindow()
        ok = not img.isNull() and img.save(path)
        print(("saved " if ok else "FAILED to save ") + path, flush=True)
        app.exit(0 if ok else 3)
    QTimer.singleShot(delay_ms, (lambda: window.shoot(path)) if threaded else grab)
