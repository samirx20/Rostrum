# Scrub and playback cost in the real 3D window (a background window at 1646 x 900, never focused): a real press-drag-
# release along the ruler, every frame, and per move the GUI thread's processor time (thread cycles, not wall time: the
# machine is shared). Two scenes:
#   "keys"  a normal scene: a plinth, a keyed ball that moves across it, a light, a camera; the ball selected (its panel
#           rows and its gizmo change every frame), then the plinth selected (nothing about it changes)
#   "buds"  brief 25's twelve buds falling into a bowl, simulated and stored; the copies selected, then the bowl
# Then playback for 3 s: the GUI thread's ms per played frame and the frames shown per second.
# SCRUB_PROFILE=1 adds a cProfile of the first scrub per scene (scrub-profile-<scene>.txt).
# The lead runs it:  heavy.ps1 run "sam: scrub profile" gpu <venv python> apps\3d\tools\scrub_profile.py <out folder>
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-scrub-cloth")
LABEL = sys.argv[2] if len(sys.argv) > 2 else "run"
sys.argv = sys.argv[:1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "app" / "tests"))
import clay_walk as W  # noqa: E402  (puts this checkout's code first; thread-cycle timers, pump)
import copies_walk as CW  # noqa: E402

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402

import main as app3d  # noqa: E402

SIZE = (1646, 900)
KEYS = '''
mat = material("mat", baseColor="#c8a050", roughness=0.4)
stone = material("stone", baseColor="#8a8a90", roughness=0.7)
cam = camera("cam", focalLength=35, x=0, y=1.2, z=2.6).aim((0, 0.4, 0))
light("key", kind="rect", x=-1.2, y=2.2, z=1.6)
mesh("plinth", shape="box", width=0.8, height=0.4, depth=0.8, y=0.2, material=stone, name="Plinth")
ball = mesh("ball", shape="sphere", radius=0.08, x=-0.5, y=0.48, material=mat, name="Ball")
ball.key("x", {0: -0.5, 2.5: 0.5, 5: -0.5})
ball.key("y", {0: 0.48, 2.5: 0.8, 5: 0.48})
ball.key("ry", {0: 0, 5: 360})
shot("hero", name="Hero 01", camera=cam, fps=24, start=0, end=5)
'''
BUDS = '''
bowlmat = material("bowlmat", baseColor="#5a7da8", roughness=0.35)
budmat = material("budmat", baseColor="#e0a43a", roughness=0.5)
cam = camera("cam", focalLength=35, x=0, y=2.35, z=1.25).aim((0, 0.3, 0))
light("key", kind="rect", x=-1.2, y=2.2, z=1.6)
bud = mesh("bud", shape="sphere", radius=0.03, material=budmat, name="Bud")
copies("buds", bud, layout="line", count=12, spacingX=0.07, x=-0.385, y=1.1, name="Buds").simulate("falls")
bowl = combine("bowl", op="subtract", name="Bowl", material=bowlmat)
with bowl:
    mesh("bowl_outer", shape="sphere", radius=0.45, y=0.45)
    mesh("bowl_inner", shape="sphere", radius=0.42, y=0.46)
    mesh("bowl_lid", shape="box", width=1.2, height=0.6, depth=1.2, y=0.9)
bowl.simulate("still")
shot("drop03", name="Drop 03", camera=cam, fps=24, start=0, end=5)
'''
NUMBERS: dict = {}


def cycles_per_ms():
    """This thread's cycles per real ms (QueryThreadCycleTime counts at the chip's own rate, ~3 GHz here, not 1 GHz):
    a busy half second, the highest of three."""
    best = 0.0
    for _ in range(3):
        c0, t0 = W.gui_cycles_ms(), time.perf_counter()
        while time.perf_counter() - t0 < 0.3:
            pass
        best = max(best, (W.gui_cycles_ms() - c0) / ((time.perf_counter() - t0) * 1000))
    return best


RATE = [1.0]


def cpu_ms():
    """The GUI thread's processor time so far, real ms."""
    return W.gui_cycles_ms() / RATE[0]


def stats(xs):
    xs = sorted(xs)
    return {"n": len(xs), "median": round(xs[len(xs) // 2], 2), "p90": round(xs[int(len(xs) * 0.9)], 2),
            "max": round(xs[-1], 2)} if xs else {"n": 0}


def find_class(root, name):
    stack = [root]
    while stack:
        it = stack.pop()
        if it.isVisible() and it.metaObject().className().startswith(name):
            return it
        stack += it.childItems()
    return None


def ruler_x(ruler, frame, fps, frames):
    p0 = ruler.mapToScene(QPointF(0, ruler.height() / 2))
    dur = ruler.property("duration") or frames / fps
    return QPoint(round(p0.x() + (frame / fps) / dur * (ruler.width() - 3)), round(p0.y()))


def scrub(w, fps, frames, name):
    """A real drag along the ruler, one move per frame; the GUI thread's processor ms per move: the move handled, the
    picture drawn, and everything it set off until the next move (`handled`: the move and the queue right after it)."""
    ruler = find_class(w.win.contentItem(), "TimeRuler")
    W.check(ruler is not None, "the timeline's ruler is on screen")
    if ruler is None:
        return {}
    v, gui, first, pic = w.v, [], [], 0
    at = ruler_x(ruler, 0, fps, frames)
    QTest.mouseMove(w.win, at)
    QTest.mousePress(w.win, Qt.LeftButton, Qt.NoModifier, at)
    W.pump(0.3)
    prof = None
    if os.environ.get("SCRUB_PROFILE"):
        import cProfile
        prof = cProfile.Profile()
        prof.enable()
    for f in range(1, frames):
        serial = v.serial
        c0 = cpu_ms()
        QTest.mouseMove(w.win, ruler_x(ruler, f, fps, frames))
        W.pump(0)
        first.append(cpu_ms() - c0)
        t0 = time.perf_counter()
        while v.serial == serial and time.perf_counter() - t0 < 0.5:     # the picture for this frame
            W.pump(0.002)
        pic += v.serial != serial
        W.pump(0.03)                                                     # and what it set off (gizmo, a 2nd paint)
        gui.append(cpu_ms() - c0)
    if prof is not None:
        import io
        import pstats
        prof.disable()
        out = io.StringIO()
        pstats.Stats(prof, stream=out).sort_stats("cumulative").print_stats(60)
        out.write("\n\n--- by own time\n")
        pstats.Stats(prof, stream=out).sort_stats("tottime").print_stats(40)
        (OUT / f"scrub-profile-{LABEL}-{name}.txt").write_text(out.getvalue(), encoding="utf-8")
    QTest.mouseRelease(w.win, Qt.LeftButton, Qt.NoModifier, ruler_x(ruler, frames - 1, fps, frames))
    W.pump(0.3)
    res = {"guiMsPerMove": stats(gui), "handledMs": stats(first), "pictures": pic}
    print(name, res, flush=True)
    return res


def playback(w, seconds=3.0):
    """Play for `seconds`: the GUI thread's ms per played frame, and the frames reached per second."""
    b = w.b
    f0, c0, t0 = b.frame, cpu_ms(), time.perf_counter()
    b.togglePlay()
    W.pump(seconds)
    b.togglePlay()
    dt, ms = time.perf_counter() - t0, cpu_ms() - c0
    n = (b.frame - f0) % (b._info["end"] - b._info["start"] + 1)
    res = {"framesPerSecond": round(n / dt, 1), "guiMsPerFrame": round(ms / max(n, 1), 2)}
    print("playback", res, flush=True)
    return res


def select(w, item_id):
    row = W.find(w.win.contentItem(), f"sceneRow:{item_id}")
    if row is not None:
        W.click(w.win, row)
    else:                                   # its row scrolled out of the list: picked without a click (not measured)
        w.b.select(item_id)
    W.pump(1, lambda: w.b.selected == item_id)
    if w.b.selected != item_id:              # the click landed on the list's edge: picked without a click (not measured)
        W.FAILS.pop()
        w.b.select(item_id)
    W.check(w.b.selected == item_id, f"{item_id} selected")
    W.pump(0.5)


def run_scene(app, name, source, shot, prepare, picks):
    project = Path(tempfile.mkdtemp(prefix=f"rostrum-scrub-{name}-"))
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script(f"{name}.py", run_source(source, f"{name}.py"))
    doc.save()
    screen = app3d.Screen(SIZE)
    res = {}
    try:
        screen.show(doc, shot_id=shot, autosave=True)
        w = CW.Walk(screen, OUT)
        W.pump(90, screen.ready, "the first picture")
        prepare(w, doc)
        info = w.b.shot_info()
        fps, frames = info["fps"], info["end"] - info["start"] + 1
        for i, pick in enumerate(picks):
            select(w, pick(doc))
            if i == 0:
                scrub(w, fps, frames, f"{name}-warm")        # shaders, caches: the first pass is not the number
            res[f"scrub:{pick(doc)}"] = scrub(w, fps, frames, f"{name}-{pick(doc)}")
        res["playback"] = playback(w)
        w.win.grabWindow().save(str(OUT / f"scrub-{LABEL}-{name}.png"))
    finally:
        screen.close()
        app.processEvents()
        shutil.rmtree(project, ignore_errors=True)
    return res


def buds_prepare(w, doc):
    """The bowl stays still, twelve buds in a line fall (the script; sim25_walk.py tries the menus): simulated, stored."""
    sim = w.b.sim
    W.pump(5, lambda: sim.canRun or sim.state == "stored", "Simulate offered (or the fall already stored)")
    if sim.canRun:
        sim.simulate()
    W.pump(180, lambda: sim.state in ("stored", "failed"), "the simulation stored")
    W.check(sim.state == "stored", f"stored ({sim.state}: {sim.label})")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    app = qt_app()
    RATE[0] = cycles_per_ms()
    NUMBERS["cyclesPerMs"] = round(RATE[0], 1)
    print("cycles per ms", NUMBERS["cyclesPerMs"], flush=True)
    NUMBERS["keys"] = run_scene(app, "keys", KEYS, "hero", lambda w, d: None, [lambda d: "ball", lambda d: "plinth"])
    NUMBERS["buds"] = run_scene(app, "buds", BUDS, "drop03", buds_prepare, [lambda d: "buds", lambda d: "bowl"])
    NUMBERS["fails"] = list(W.FAILS)
    (OUT / f"scrub-{LABEL}.json").write_text(json.dumps(NUMBERS, indent=2), encoding="utf-8")
    print("FAILS:" if W.FAILS else "ALL PASSED", *W.FAILS, sep="\n  ")
    sys.exit(1 if W.FAILS else 0)


if __name__ == "__main__":
    main()
