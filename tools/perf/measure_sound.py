"""How fast RostrumSound's real window answers, drawn offscreen (S59). Each step is timed with perf_counter from the
action to the drawn frame (win.grabWindow draws it), as median and worst of N repeats.

    python tools/perf/measure_sound.py [--n 20]           # the table
    python tools/perf/measure_sound.py --soak 300         # memory (RSS) over 5 minutes of the same steps, looped
    python tools/perf/measure_sound.py --profile select   # cProfile of one step's repeats (top 25 by own+callee time)
"""
import argparse
import ctypes
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

T0 = time.perf_counter()
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "apps" / "sound" / "screen")]
os.environ.update({"QT_QPA_PLATFORM": "offscreen", "QT_QPA_FONTDIR": "C:/Windows/Fonts",
                   "QT_ENABLE_HIGHDPI_SCALING": "0"})
import main as sound_main  # noqa: E402  (this checkout's code: main.py calls checkout_paths first)
from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound.sample import SOURCE  # noqa: E402
from screensound.steps import wait_render  # noqa: E402
T_IMPORTS = time.perf_counter()

# The sample song plus 12 busy tracks (a real song's size: ~800 notes), so cost that grows with the song shows.
BIG = SOURCE + "\n".join(
    f'x{k} = track("extra{k}", synth="saw", volume=0.3)\n'
    f'for n in range(64):\n    x{k}.note(["C4","E4","G4","B4"][n % 4], at=beat(n * 0.5), dur=beats(0.5), vel=0.5)'
    for k in range(12))


def rss_mb() -> float:
    class PMC(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
            (n, ctypes.c_size_t) for n in ("Peak", "WS", "QPPeak", "QP", "QNPPeak", "QNP", "Page", "PeakPage")]
    c = PMC(cb=ctypes.sizeof(PMC))
    k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.WS / 2**20


def draw(win):
    """Let queued work run, then draw one frame: the change is on screen when this returns. deleteLater runs too (as the
    app's own event loop does; processEvents alone leaves every closed window alive)."""
    QCoreApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    if win.grabWindow().isNull():
        raise RuntimeError("the window gave no picture")


def timed(screen, act) -> float:
    t = time.perf_counter()
    act()
    draw(screen.win)                                   # the window now shown (opening a song makes a new one)
    return (time.perf_counter() - t) * 1000


def wait(cond, what, limit=30.0):
    end = time.monotonic() + limit
    while not cond():
        if time.monotonic() > end:
            raise RuntimeError(f"{what}: nothing after {limit:g} s")
        QCoreApplication.processEvents()
        time.sleep(0.001)


def play_ms(screen) -> float:
    """Play pressed → the engine says playing and the playhead has moved; then stop."""
    b = screen.bridge
    wait_render(b)
    b.setTime(0.0)
    draw(screen.win)
    t = time.perf_counter()
    b.togglePlay()
    wait(lambda: b.playing and b.time > 0.0, "play")
    draw(screen.win)
    ms = (time.perf_counter() - t) * 1000
    b.togglePlay()
    draw(screen.win)
    return ms


def steps(screen, song):
    """name -> one repeat (returns ms). The same actions a person makes, through the bridge calls QML makes."""
    b = lambda: screen.bridge  # noqa: E731  (opening a song makes a new bridge)
    ids = [n["id"] for t in b().doc.data["tracks"] for n in t.get("notes", [])][:40]
    firsts = [t["notes"][0]["id"] for t in b().doc.data["tracks"] if t.get("notes")]     # one per track
    flip = {"i": 0}

    def nxt():
        flip["i"] += 1
        return flip["i"]
    return {
        "open song": lambda: timed(screen, lambda: screen.files.openPath(str(song))),
        "play start": lambda: play_ms(screen),
        "scroll": lambda: timed(screen, lambda: b().setViewStart(2.0 if nxt() % 2 else 0.0)),
        "zoom": lambda: timed(screen, lambda: b().zoomAt(1.25 if nxt() % 2 else 0.8, 0.5)),
        "open mixer": lambda: (timed(screen, lambda: b().workspace.setDock("mixer")),
                               b().workspace.setDock("editor"), draw(screen.win))[0],
        "open editor": lambda: (b().workspace.setDock("mixer"), draw(screen.win),
                                timed(screen, lambda: b().workspace.setDock("editor")))[2],
        "select clip": lambda: timed(screen, lambda: b().select(ids[nxt() % len(ids)])),
        "select other track": lambda: timed(screen, lambda: b().select(firsts[nxt() % len(firsts)])),
    }


def make_song(folder) -> Path:
    doc = Document.new(KIND, folder=folder, item="perf")
    doc.run_script("perf.py", run_source(BIG, "perf.py"))
    doc.save()
    return Path(folder)


def start(folder):
    """App start → window shown and arrangement drawn, split in imports / QML load / first draw."""
    app = qt_app()
    song = make_song(folder)
    t = time.perf_counter()
    screen = sound_main.Screen()
    screen.files.openPath(str(song))
    t_qml = time.perf_counter()
    draw(screen.win)
    t_draw = time.perf_counter()
    split = {"imports": T_IMPORTS - T0, "QML load (open song + window)": t_qml - t, "first draw": t_draw - t_qml}
    return app, screen, song, split


def table(screen, song, n, only=None):
    rows = {}
    for name, fn in steps(screen, song).items():
        if only and name not in only.split(","):
            continue
        fn()                                           # one warm-up (first use of a panel)
        ms = [fn() for _ in range(n)]
        rows[name] = (statistics.median(ms), max(ms))
        print(f"{name:14s} median {rows[name][0]:8.1f} ms   worst {rows[name][1]:8.1f} ms", flush=True)
    return rows


def soak(screen, song, seconds):
    run, t0, base, nxt = steps(screen, song), time.monotonic(), rss_mb(), 0
    print(f"RSS start {base:.0f} MB", flush=True)
    while time.monotonic() - t0 < seconds:
        for fn in run.values():
            fn()
        if time.monotonic() - t0 >= nxt:
            print(f"t={time.monotonic() - t0:5.0f}s  RSS {rss_mb():.0f} MB", flush=True)
            nxt += 30
    print(f"RSS end {rss_mb():.0f} MB (growth {rss_mb() - base:+.0f} MB)", flush=True)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--n", type=int, default=20)
    a.add_argument("--soak", type=float)
    a.add_argument("--profile")
    a.add_argument("--only", help="comma-separated step names (default: all)")
    args = a.parse_args()
    with tempfile.TemporaryDirectory(prefix="rostrum-perf-") as folder:
        app, screen, song, split = start(folder)
        total = sum(split.values()) + (T0 - _proc_start())
        print(f"start total {total * 1000:.0f} ms (process start -> drawn): " + ", ".join(
            f"{k} {v * 1000:.0f} ms" for k, v in split.items()) + f", python start {(T0 - _proc_start()) * 1000:.0f} ms", flush=True)
        try:
            if args.soak:
                soak(screen, song, args.soak)
            elif args.profile:
                import cProfile
                import pstats
                fn = steps(screen, song)[args.profile]
                fn()
                pr = cProfile.Profile()
                pr.runcall(lambda: [fn() for _ in range(args.n)])
                pstats.Stats(pr).sort_stats("cumulative").print_stats(30)
            else:
                table(screen, song, args.n, args.only)
        finally:
            screen.close()


def _proc_start() -> float:
    """This process' start on the perf_counter clock (Windows GetProcessTimes)."""
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.c_void_p] * 4
    ft = [ctypes.c_ulonglong() for _ in range(4)]
    k32.GetProcessTimes(k32.GetCurrentProcess(), *map(ctypes.byref, ft))
    now_ft = ctypes.c_ulonglong()
    ctypes.windll.kernel32.GetSystemTimePreciseAsFileTime(ctypes.byref(now_ft))
    return time.perf_counter() - (now_ft.value - ft[0].value) / 1e7


if __name__ == "__main__":
    main()
