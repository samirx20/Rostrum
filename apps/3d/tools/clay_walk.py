# Clay walk (CL1): the Clay tool tried by real input in the real window (behind the person's work, never focused).
# A scratch project with the sample scene; Q (the real key); a Lump click on the ground (a real click) makes a clay;
# then three real drags across it: Add (its tile clicked), Carve (Ctrl held: the opposite), Smooth (Shift held). Each
# pointer move is timed: the GUI thread's processor time for the move (cpu ms), the wait until the engine answered its
# dab (wall ms, and the engine's own ms), and the engine process's processor time over the dab. Each stroke must be
# exactly one undo step: one new step on the clay, gone after Ctrl+Z, back after Ctrl+Shift+Z. Pictures after each
# stroke and the numbers (clay_walk.json) go to the out folder. Needs the core built with clay; the lead runs it:
#   heavy.ps1 run "priyam: clay walk" gpu <venv python> apps\3d\tools\clay_walk.py [out folder]
# Exit 0 = every check passed; else the failed checks are printed and it exits 1.
import ctypes as ct
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
import main as app3d  # noqa: E402  (puts this checkout's code first)

from PySide6.QtCore import QCoreApplication, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d.gizmo import View  # noqa: E402
from screen3d.sample import SOURCE  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-cl1")
SIZE, BUDGET_MS = (1646, 900), 16.0
K32 = ct.windll.kernel32
K32.GetCurrentThread.restype = ct.c_void_p
K32.OpenProcess.restype = ct.c_void_p
FAILS: list[str] = []


def gui_cycles_ms():
    """This (GUI) thread's processor time so far in ms, from its cycle count at a nominal 1 GHz (QueryThreadCycleTime,
    as sound-fix-r9's drive.py: exact, unlike the 15.6 ms clock)."""
    c = ct.c_ulonglong()
    K32.QueryThreadCycleTime(ct.c_void_p(K32.GetCurrentThread()), ct.byref(c))
    return c.value / 1e6


def proc_cpu_ms(handle):
    """A process's user + kernel time so far, ms (GetProcessTimes, 100 ns units)."""
    t = [ct.c_ulonglong() for _ in range(4)]
    K32.GetProcessTimes(ct.c_void_p(handle), *(ct.byref(x) for x in t))
    return (t[2].value + t[3].value) / 1e4


def pump(seconds=0.0, until=None, what=""):
    end = time.perf_counter() + seconds
    while True:
        QCoreApplication.processEvents()
        if until is not None and until():
            return True
        if time.perf_counter() > end:
            if until is not None:
                FAILS.append(f"timed out waiting for {what}")
            return until is None
        time.sleep(0.002)


def check(ok, line):
    print(("ok   " if ok else "FAIL ") + line)
    if not ok:
        FAILS.append(line)


def find(item, name):
    """The drawn item named `name` (objectName), through the visible tree."""
    if item.objectName() == name and item.isVisible():
        return item
    for c in item.childItems():
        hit = find(c, name)
        if hit is not None:
            return hit
    return None


def centre(item):
    p = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    return QPoint(round(p.x()), round(p.y()))


def click(win, item):
    at = centre(item)
    QTest.mouseMove(win, at)
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
    pump(0.2)


def clay_on_screen(screen, clay_id, vp_item):
    """The window point of the clay's middle, and its radius in window px (to size the drags)."""
    v, frame = screen.bridge.viewport, screen.bridge.frame
    scene, cam = v.sent()
    view = View.of(cam, scene, frame, cam["width"], cam["height"])
    from rostrum3d import aim, through
    world = through.find_item(scene, clay_id, frame)[0]
    mid = aim.point(world, [0.0, 0.0, 0.0])
    x, y, depth = view.project(mid)
    to_win = 1.0 / (v._scale * vp_item.window().devicePixelRatio())
    radius_px = 0.6 * screen.bridge.doc.item(clay_id)["steps"][0].get("radius", 0.05) / view.units(depth) * to_win
    top = vp_item.mapToScene(QPointF(0, 0))
    return QPointF(top.x() + x * to_win, top.y() + y * to_win), radius_px


def stroke(screen, win, name, at, radius, mods, core):
    """One real drag across the clay; its moves timed; one undo step checked; a picture after."""
    tool, doc = screen.bridge.viewport.clay, screen.bridge.doc
    clay_id = tool.clayId
    before = len(doc.item(clay_id)["steps"])
    start = QPoint(round(at.x() - radius), round(at.y()))
    QTest.mouseMove(win, start)
    pump(0.3)
    QTest.mousePress(win, Qt.LeftButton, mods, start)
    pump(5, lambda: not tool._busy and tool._phase in ("sculpt", "orbit", ""), "the stroke's begin")
    check(tool._phase == "sculpt", f"{name}: the press on the clay began a stroke (not a view turn)")
    moves, views = [], []
    worker = screen.bridge.viewport._r
    on_ready = lambda serial, ms, *rest: views.append(round(ms, 2))  # noqa: E731  the engine's own ms per picture
    worker.ready.connect(on_ready)
    for i in range(1, 25):
        p = QPoint(round(at.x() - radius + 2 * radius * i / 24), round(at.y() + 0.25 * radius * (i % 2)))
        c0, w0, e0 = gui_cycles_ms(), time.perf_counter(), proc_cpu_ms(core)
        QTest.mouseMove(win, p)
        QCoreApplication.processEvents()
        gui = gui_cycles_ms() - c0
        n = len(tool.timings)
        pump(5, lambda: not tool._busy, "a dab's answer")
        last = tool.timings[-1] if len(tool.timings) > n else {}
        moves.append({"guiCpuMs": round(gui, 2), "wallMs": round((time.perf_counter() - w0) * 1000, 2),
                      "engineMs": last.get("engineMs"), "coreCpuMs": round(proc_cpu_ms(core) - e0, 2),
                      "dabs": last.get("dabs")})
    worker.ready.disconnect(on_ready)
    QTest.mouseRelease(win, Qt.LeftButton, mods, p)
    pump(10, lambda: not tool._ending and len(doc.item(clay_id)["steps"]) > before, "the stroke's step")
    steps = doc.item(clay_id)["steps"]
    check(len(steps) == before + 1, f"{name}: one new step on the clay ({before} -> {len(steps)})")
    want = {"Add": "add", "Carve (Ctrl)": "carve", "Smooth (Shift)": "smooth"}[name]
    check(steps[-1].get("brush") == want and str(steps[-1].get("dabs", "")).startswith("clay/"),
          f"{name}: the step is a {want} stroke with its dabs file ({steps[-1].get('brush')}, {steps[-1].get('dabs')})")
    pump(1.0)
    win.grabWindow().save(str(OUT / f"clay-walk-{want}.png"))
    QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
    pump(0.5)
    check(len(doc.item(clay_id)["steps"]) == before, f"{name}: Ctrl+Z takes back exactly the stroke")
    QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier)
    pump(0.5)
    check(len(doc.item(clay_id)["steps"]) == before + 1, f"{name}: Ctrl+Shift+Z puts it back")
    worst = max(m["wallMs"] for m in moves)
    check(worst <= BUDGET_MS * 2, f"{name}: slowest dab answered in {worst:.1f} ms (budget ~{BUDGET_MS:.0f} ms a dab)")
    return {"stroke": name, "moves": moves, "timings": tool.timings, "viewMs": views}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-claywalk-"))
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("sample.py", run_source(SOURCE, "sample.py"))
    doc.save()
    screen = app3d.Screen(SIZE)
    report = {"strokes": []}
    try:
        screen.show(doc, autosave=True)
        win, v = screen.win, screen.bridge.viewport
        pump(60, screen.ready, "the first picture")
        vp_item = find(win.contentItem(), "viewport3d")
        scene = v.sent()[0]
        core = K32.OpenProcess(0x1000, False, v._r.wait_for(lambda e: (e.ensure_scene(scene), e.pid)[1]))

        QTest.keyClick(win, Qt.Key_Q)                                   # Clay
        pump(0.3)
        check(v.clay.on and v.clay.tool == "lump", "Q turns the Clay tool on, Lump chosen (nothing to sculpt yet)")
        ground = vp_item.mapToScene(QPointF(vp_item.width() * 0.5, vp_item.height() * 0.85))
        QTest.mouseMove(win, ground.toPoint())
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, ground.toPoint())
        pump(20, lambda: v.clay.clayId != "", "the Lump click's new clay")
        clay_id = v.clay.clayId
        check(bool(clay_id), f"a Lump click on the ground made a clay ({clay_id}), selected")
        serial = v.serial
        pump(30, lambda: v.serial > serial and not v.status.startswith("Error"), "the clay drawn")
        check(not v.status.startswith("Error"), f"the clay draws ({v.status or 'no error'})")
        win.grabWindow().save(str(OUT / "clay-walk-lump.png"))

        add = find(win.contentItem(), "clayBrushAdd")
        check(add is not None, "the Add tile is on the panel")
        click(win, add)
        check(v.clay.tool == "add", "clicking Add chooses it (the clay's brush)")
        at, radius = clay_on_screen(screen, clay_id, vp_item)
        info0 = v._r.wait_for(lambda e: e.clay_info(clay_id))
        idle = []                                          # the same picture with nothing changing: the scene's own cost
        grab = lambda serial, ms, *rest: idle.append(round(ms, 2))  # noqa: E731
        v._r.ready.connect(grab)
        for _ in range(8):
            v.redraw()
            pump(2, lambda: len(idle) > _, "an idle picture")
        v._r.ready.disconnect(grab)
        report["idleViewMs"] = idle
        for name, mods in (("Add", Qt.NoModifier), ("Carve (Ctrl)", Qt.ControlModifier), ("Smooth (Shift)", Qt.ShiftModifier)):
            report["strokes"].append(stroke(screen, win, name, at, radius, mods, core))
        info1 = v._r.wait_for(lambda e: e.clay_info(clay_id))
        check(info1.get("hash") != info0.get("hash"), f"the clay's shape changed ({info0.get('hash')} -> {info1.get('hash')})")
        report["clayInfo"] = {"before": info0, "after": info1}
        K32.CloseHandle(ct.c_void_p(core))
    except Exception as e:  # noqa: BLE001  a crash is a failed walk, said with its reason
        FAILS.append(f"the walk stopped: {type(e).__name__}: {e}")
    finally:
        report["fails"] = FAILS
        (OUT / "clay_walk.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        screen.close()
        pump(1.0)
        shutil.rmtree(project, ignore_errors=True)
    print(f"{len(FAILS)} failed check(s); numbers and pictures in {OUT}")
    for f in FAILS:
        print("  " + f)
    app.quit()
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
