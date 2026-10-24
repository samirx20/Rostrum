"""What one edit costs the screen's own thread in Rostrum2D's real window, per edit kind and per part.

    python tools/perf/edit_cost.py [sample|busy] [N]           # median / worst ms per edit kind
    python tools/perf/edit_cost.py [sample|busy] profile KIND  # where the time goes (cProfile; signal reactions by caller)

The real window (QT_QPA_PLATFORM=windows), opened behind the person's work (ROSTRUM_BACKGROUND_WINDOWS=1). "busy" is a
saved project with 60 layers, a drawing with paint, keys and markers. Each edit is driven through the slots the
canvas and panel call; its cost is the act plus every event it queued, on the GUI thread, until the thread is idle
(the engine's picture is made on its own thread and is not counted; its arrival is, as part of the next idle wait).
"""
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "apps/2d/screen")]
os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ["ROSTRUM_BACKGROUND_WINDOWS"] = "1"
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
import checkout_paths  # noqa: E402

checkout_paths.use_this_checkout()


def busy_source(n=60) -> str:
    s = ['comp("busy", name="Busy scene", width=1920, height=1080, fps=30, duration=8, background="#101418")']
    for i in range(n - 12):
        s.append(f'l{i} = shape("s{i}", w={80 + i % 7 * 20}, h=60, radius=8, fill="#{(i * 37) % 255:02x}80c0", '
                 f'x={100 + (i * 97) % 1700}, y={100 + (i * 53) % 880})')
        if i % 4 == 0:
            s.append(f'l{i}.key("x", {{0.0: {100 + i}, 2.0: {900 + i}}}, ease="snappy")')
    for i in range(8):
        s.append(f'text("t{i}", body="Title {i} goes here", size=48, x={300 + 150 * i}, y={900 - 60 * i})')
    s.append('with group("g", x=960, y=540, w=400, h=200):')
    for i in range(3):
        s.append(f'    shape("gs{i}", w=40, h=40, x={60 + 100 * i}, y=100)')
    s.append('d = drawing("pad", w=1920, h=1080)')
    s.append('f = d.frame(0)')
    s.append('p = f.paint()')
    for k in range(30):
        pts = [[200 + 40 * k + 6 * j, 300 + 5 * j, 1.0] for j in range(30)]
        s.append(f'p.stroke({pts}, color="#ffaa33", size=12, brush="round")')
    return "\n".join(s) + "\n"


def _cycles() -> int:
    """This thread's CPU cycles so far (Windows QueryThreadCycleTime: exact, where thread_time steps by 15.6 ms)."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.windll.kernel32
    k32.GetCurrentThread.restype = wintypes.HANDLE
    k32.QueryThreadCycleTime.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_ulonglong)]
    n = ctypes.c_ulonglong()
    k32.QueryThreadCycleTime(k32.GetCurrentThread(), ctypes.byref(n))
    return n.value


_PER_MS = []


def thread_ms() -> float:
    """This thread's CPU time in ms, from its cycle count (cycles per ms measured once on a busy loop)."""
    if not _PER_MS:
        best = 0.0
        for _ in range(5):
            c, t = _cycles(), time.perf_counter()
            while time.perf_counter() - t < 0.02:
                pass
            best = max(best, (_cycles() - c) / ((time.perf_counter() - t) * 1000))
        _PER_MS.append(best)
    return _cycles() / _PER_MS[0]


class Rig:
    def __init__(self, scene):
        from rostrum_gui.app import qt_app
        self.app = qt_app()
        from screen2d.session import Session
        self.session = Session((1646, 900))
        from rostrum_core import Document
        from rostrum2d import KIND, run_source
        from screen2d.files2d import ITEM
        from screen2d.sample import SOURCE
        source = SOURCE if scene == "sample" else busy_source()
        folder = Path(tempfile.mkdtemp(prefix="rostrum-edit-cost-")) / scene.title()
        doc = Document.new(KIND, folder=folder, item=ITEM)
        doc.run_script(f"{scene}.py", run_source(source, f"{scene}.py"))
        doc.save()
        self.session.files.put(doc)
        self.layer, self.drawing = ("card", None) if scene == "sample" else ("s5", "pad")
        self.idle(3.0)

    @property
    def b(self):
        return self.session.bridge

    def events(self):
        from PySide6.QtCore import QCoreApplication, QEvent
        self.app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def idle(self, settle=0.25):
        """Events until the frame worker is idle and `settle` s have passed with it idle."""
        end = time.perf_counter() + 20
        quiet = None
        while time.perf_counter() < end:
            self.events()
            if self.b.frames.idle():
                quiet = quiet or time.perf_counter()
                if time.perf_counter() - quiet > settle:
                    return
            else:
                quiet = None
            time.sleep(0.002)
        raise RuntimeError("the screen never went idle")

    def cost(self, act) -> float:
        """GUI-thread ms of `act` plus the events it queued (processed at once, as the loop would). CPU time of this
        thread (time.thread_time) when CPU=1 (the default): the machine is shared, and other programs' load stretched
        wall times 2-10x; the thread's own CPU is what the edit costs. CPU=0: wall time."""
        clock = thread_ms if os.environ.get("CPU", "1") == "1" else time.perf_counter
        t = clock()
        act()
        self.events()
        self.events()
        return (clock() - t) * (1 if clock is thread_ms else 1000)

    # ---- edit kinds: each returns its act (what is timed), after doing any set-up untimed ----------------------
    def field(self, i):
        self.b.select(self.layer)
        return lambda: self.b.setValue("opacity", 0.5 + (i % 5) / 10)

    def drag_end(self, i):
        b = self.b
        b.select(self.layer)
        assert b.beginMove(), "the drag did not start"
        for k in range(4):
            b.moveBy(3.0 * (k + 1), 2.0 * (k + 1))
            self.events()
        return b.endDrag

    def key_add(self, i):
        self.b.select(self.layer)
        self.b.setTime(0.5 + (i % 6) * 0.3)
        return lambda: self.b.toggleAnimate("y")

    def stroke(self, i):
        if not self.drawing:
            return None
        b, p = self.b, self.b.painter
        b.select(self.drawing)
        b.setTool("draw")
        assert p.beginStroke(300 + i * 7, 300, 1.0), "the stroke did not start"
        for k in range(12):
            p.strokeTo(300 + i * 7 + k * 9, 300 + k * 4, 1.0)
            self.events()
        return p.endStroke

    def undo(self, i):
        self.b.select(self.layer)
        self.b.setValue("rotation", 3 + i)
        self.idle(0.1)
        return self.b.undo

    KINDS = ("field", "drag_end", "key_add", "stroke", "undo")

    def run(self, kind, n):
        out = []
        for i in range(n):
            act = getattr(self, kind)(i)
            if act is None:
                return None
            self.idle(0.1)
            out.append(self.cost(act))
            self.idle(0.15)
        return out

    def close(self):
        self.session.close() if hasattr(self.session, "close") else None


def profile(rig, kind, n=8):
    import cProfile
    import pstats
    p = cProfile.Profile()
    rig.prof = p
    for i in range(n):
        act = getattr(rig, kind)(i)
        rig.idle(0.1)
        p.enable()
        rig.cost(act)
        p.disable()
        rig.idle(0.15)
    st = pstats.Stats(p, stream=sys.stdout)
    st.sort_stats("cumulative").print_stats(60)
    st.print_callers(r"\{method 'emit'")
    for f in sys.argv[4:]:
        st.print_callees(f)


class Sampler:
    """The GUI thread's Python stack every ~0.5 ms while an edit runs (cProfile in 3.12 watches every thread)."""

    def __init__(self):
        import threading
        self.main, self.stacks, self.on = threading.get_ident(), [], False

    def __enter__(self):
        import threading
        self.on = True
        self.th = threading.Thread(target=self._run, daemon=True)
        self.th.start()
        return self

    def __exit__(self, *a):
        self.on = False
        self.th.join()

    def _run(self):
        while self.on:
            f = sys._current_frames().get(self.main)
            st = []
            while f is not None:
                c = f.f_code
                st.append((c.co_filename.replace(str(ROOT), "").lstrip("\\/"), c.co_name, f.f_lineno))
                f = f.f_back
            self.stacks.append(st)
            time.sleep(0.0005)


def parts(rig, kind, n=10, make=None):
    """Where the GUI thread's time goes per edit: inclusive share of each named part, then the innermost lines."""
    from collections import Counter
    total, smp = 0.0, Sampler()
    for i in range(n):
        act = make(i) if make else getattr(rig, kind)(i)
        rig.idle(0.1)
        with Sampler() as s:
            total += rig.cost(act)
        smp.stacks += s.stacks
        rig.idle(0.15)
    per = total / n
    N = max(len(smp.stacks), 1)
    inc, leaf = Counter(), Counter()
    under = os.environ.get("UNDER")             # only what runs inside this part (file:function), e.g. bridge.py:_heard
    if under:
        cut = []
        for st in smp.stacks:
            names = [f"{Path(fn).name}:{name}" for fn, name, _ in st]
            if under in names:
                cut.append(st[:names.index(under) + 1])
        smp.stacks = cut
    for st in smp.stacks:
        seen = set()
        for fn, name, line in st:
            k = f"{Path(fn).name}:{name}"
            if k not in seen:
                inc[k] += 1
                seen.add(k)
        ours = [(fn, name, line) for fn, name, line in st if not fn.startswith(("C:", "<"))]
        if ours:
            fn, name, line = ours[0]
            leaf[f"{Path(fn).name}:{name}:{line}"] += 1
    print(f"{kind}: {per:.1f} ms per edit, {N} samples" + (f" (under {under}; shares of all samples)" if under else ""))
    print("-- inclusive (ms per edit)")
    for k, c in inc.most_common(70):
        print(f"{c / N * per:7.1f}  {k}")
    print("-- innermost repo line (ms per edit)")
    for k, c in leaf.most_common(40):
        print(f"{c / N * per:7.1f}  {k}")


def all_signals(rig):
    """[(name, SignalInstance)]: every argument-less signal of the bridge and its parts."""
    from PySide6.QtCore import QObject, SignalInstance
    b = rig.b
    found = [("bridge", b)] + [(k, v) for k, v in vars(b).items() if isinstance(v, QObject)]
    kit = b._kit
    found += [(f"_kit.{k}", getattr(kit, k)) for k in getattr(kit, "__slots__", ()) if isinstance(getattr(kit, k, None), QObject)]
    out = []
    for owner, obj in found:
        mo = obj.metaObject()
        for i in range(mo.methodOffset() if owner != "bridge" else QObject.staticMetaObject.methodCount(), mo.methodCount()):
            m = mo.method(i)
            if m.methodType().name != "Signal" or m.parameterCount():
                continue
            name = bytes(m.name()).decode()
            sig = getattr(obj, name, None)
            if isinstance(sig, SignalInstance):
                out.append((f"{owner}.{name}", sig))
    return out


def fired(rig, kind, n=15):
    """Which signals one edit of `kind` sends (times), and each one's own reaction cost when emitted alone."""
    from collections import Counter
    sigs, hits = all_signals(rig), Counter()
    for name, sig in sigs:
        sig.connect(lambda name=name: hits.update([name]))
    act = getattr(rig, kind)(0)
    rig.idle(0.1)
    hits.clear()
    rig.cost(act)
    got = dict(hits)
    rig.idle(0.2)
    rows = []
    for name, sig in sigs:
        if name not in got:
            continue
        ms = []
        for _ in range(n):
            t = time.perf_counter()
            sig.emit()
            rig.events()
            ms.append((time.perf_counter() - t) * 1000)
        rows.append((statistics.median(ms) * got[name], got[name], name))
        rig.idle(0.05)
    print(f"{kind}: signals sent by one edit (x times), cost of each alone")
    for total, k, name in sorted(rows, reverse=True):
        print(f"{total:7.2f} ms  x{k}  {name}")


def signals(rig, n=15):
    """Each signal a change sends, emitted alone: what its listeners (QML and Python) cost, ms per emit."""
    from PySide6.QtCore import QObject, SignalInstance
    b = rig.b
    b.select(rig.layer)
    rig.idle(0.2)
    found = [("bridge", b)] + [(k, v) for k, v in vars(b).items() if isinstance(v, QObject)]
    kit = b._kit
    found += [(f"_kit.{k}", getattr(kit, k)) for k in getattr(kit, "__slots__", ()) if isinstance(getattr(kit, k, None), QObject)]
    rows = []
    for owner, obj in found:
        mo = obj.metaObject()
        for i in range(mo.methodOffset() if owner != "bridge" else QObject.staticMetaObject.methodCount(), mo.methodCount()):
            m = mo.method(i)
            if m.methodType().name != "Signal" or m.parameterCount():
                continue
            name = bytes(m.name()).decode()
            sig = getattr(obj, name, None)
            if not isinstance(sig, SignalInstance):
                continue
            ms = []
            for _ in range(n):
                t = time.perf_counter()
                sig.emit()
                rig.events()
                ms.append((time.perf_counter() - t) * 1000)
            rows.append((statistics.median(ms), f"{owner}.{name}"))
            rig.idle(0.05)
    for med, name in sorted(rows, reverse=True)[:40]:
        print(f"{med:7.2f} ms  {name}")


def qml_tree(rig, depth=6):
    """The window's QML items (class names, depth first) up to `depth`: where to look for a reaction's cost."""
    out = []

    def walk(item, d, path):
        name = item.metaObject().className().split("_QML")[0]
        out.append((path + "/" + name, item))
        if d < depth:
            for c in item.childItems():
                walk(c, d + 1, path + "/" + name)
    walk(rig.session.win.contentItem(), 0, "")
    return out


def bisect(rig, signal, n=15):
    """The cost of `signal` alone, then with each big QML piece hidden (visible false; a hidden piece still binds, so
    a drop means its layout / drawing work) and with each piece's `bridge` / `backend` cut (its bindings stop)."""
    b = rig.b
    b.select(rig.layer)
    rig.idle(0.2)
    obj = b if "." not in signal else getattr(b, signal.split(".")[0])
    sig = getattr(obj, signal.split(".")[-1])

    def cost():
        ms = []
        for _ in range(n):
            t = time.perf_counter()
            sig.emit()
            rig.events()
            ms.append((time.perf_counter() - t) * 1000)
        return statistics.median(ms)
    base = cost()
    print(f"{signal}: {base:.2f} ms")
    for path, item in qml_tree(rig, int(os.environ.get("DEPTH", "5"))):
        if not item.isVisible() or item.width() * item.height() < 2000:
            continue
        item.setVisible(False)
        rig.events()
        c = cost()
        item.setVisible(True)
        rig.events()
        if base - c > 0.4:
            print(f"  hidden {base - c:5.2f} ms less  {path}")


def main():
    scene = sys.argv[1] if len(sys.argv) > 1 else "sample"
    rig = Rig(scene)
    try:
        if len(sys.argv) > 2 and sys.argv[2] == "parts":
            for k in sys.argv[3:] or Rig.KINDS:
                parts(rig, k)
            return
        if len(sys.argv) > 2 and sys.argv[2] == "emit":       # emit KIND-less: one signal alone, sampled
            obj = rig.b if "." not in sys.argv[3] else getattr(rig.b, sys.argv[3].split(".")[0])
            rig.b.select(rig.layer)
            parts(rig, sys.argv[3], 20, lambda i: getattr(obj, sys.argv[3].split(".")[-1]).emit)
            return
        if len(sys.argv) > 2 and sys.argv[2] == "fired":
            for k in sys.argv[3:] or Rig.KINDS:
                fired(rig, k)
            return
        if len(sys.argv) > 2 and sys.argv[2] == "bisect":
            bisect(rig, sys.argv[3])
            return
        if len(sys.argv) > 2 and sys.argv[2] == "signals":
            signals(rig)
            return
        if len(sys.argv) > 2 and sys.argv[2] == "profile":
            profile(rig, sys.argv[3])
            return
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
        print(f"scene {scene}: {len(rig.b.doc.data['comps'][0].get('layers', []))} top layers")
        for kind in Rig.KINDS:
            ms = rig.run(kind, n)
            if ms is None:
                print(f"{kind:9s}  (no drawing in this scene)")
                continue
            print(f"{kind:9s}  median {statistics.median(ms):6.1f} ms   worst {max(ms):6.1f} ms   (n={len(ms)})", flush=True)
    finally:
        rig.close()


if __name__ == "__main__":
    main()
