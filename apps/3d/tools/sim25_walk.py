# Brief 25 walk (rigid bodies): "Drop 03" tried by real input in the real window (a background window at 1646 x 900,
# never focused). Real mouse and keys on visible controls found by objectName; the document is only read, to CHECK
# (a typed number that reaches no text box in a background window falls back to the bridge's setValue: KNOWN OPEN, as in
# copies_walk.py). A scratch project: a bowl (a combine: a sphere minus a smaller sphere minus a box over the top), a bud
# (a small sphere) above it, shot "Drop 03" (120 frames at 24 fps). Then:
#   1. right-click the bowl's row › Simulate › Stays still (one undo step) ............................. "1-bowl-still"
#   2. right-click the bud's row › Make copies › Line; Count 12, Space X typed; right-click the copies' row ›
#      Simulate › Falls (one undo step): the falling-arrow badge, the Simulate row "Not computed" ...... "2-not-computed"
#   3. a click on Simulate in the row: the bar fills (a picture mid-way when the job is slow enough to catch), then
#      "Stored · 120 frames"; one undo step for the record ................................................ "3-filling", "4-stored"
#   4. scrubbing: a real drag along the ruler; per move the GUI thread's ms (thread cycles) and move -> next picture ms
#      (the engine reading the stored result); three moments of the fall ............................... "5-fall-a/b/c"
#   5. the bowl moved (its X typed): the row "Out of date", striped; the viewport keeps the old result
#      (the shot's simKey unchanged) .................................................................... "6-out-of-date"
#   4b. (26a) nothing selected (Esc): the Scene panel's Timing set On 2s by real clicks (the result read back holds each
#      pose 2 frames: the copies' `sim` step and the ball's keys-to-be, bridge read only); Turn into keys by a real click
#      (one undo step: the ball has keys and is Off; the buds, a copies item, keep simulating); the ball's last y key
#      nudged (a document operation), Simulate again: the nudge stays .......................... "5d-on-2s", "5e-keys"
#   6. the buds moved down into the bowl's bottom (the copies' Y typed), Simulate: the core's failure in red in the row
#      (which body, which frame, what to do) ............................................................ "7-failed"
# Numbers and checks to sim25_walk.json. Needs the core built with brief 25 (Jolt). The lead runs it:
#   heavy.ps1 run "sam: 3d-25 walk" gpu <venv python> apps\3d\tools\sim25_walk.py [out folder]
# Exit 0 = every check passed; else the failed checks are printed and it exits 1.
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-25")
sys.argv = sys.argv[:1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "app" / "tests"))
import clay_walk as W  # noqa: E402  (puts this checkout's code first; its real-input helpers and thread-cycle timers)
import copies_walk as CW  # noqa: E402  (right-click, menus, typing into a row)
import clay_paint_walk as CP  # noqa: E402  (find_text)

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402

import main as app3d  # noqa: E402
from screen3d import outline  # noqa: E402

SIZE = (1646, 900)
SPACING = 0.07                  # metres between buds (typed into Space X): apart, so none starts inside another
SCENE = '''
bowlmat = material("bowlmat", baseColor="#5a7da8", roughness=0.35)
budmat = material("budmat", baseColor="#e0a43a", roughness=0.5)
cam = camera("cam", focalLength=35, x=0, y=2.35, z=1.25).aim((0, 0.3, 0))
light("key", kind="rect", x=-1.2, y=2.2, z=1.6)
mesh("bud", shape="sphere", radius=0.03, x=-0.385, y=1.1, material=budmat, name="Bud")
mesh("ball", shape="sphere", radius=0.04, x=0.15, y=1.3, z=0.12, material=budmat, name="Ball")
with combine("bowl", op="subtract", name="Bowl", material=bowlmat):
    mesh("bowl_outer", shape="sphere", radius=0.45, y=0.45)
    mesh("bowl_inner", shape="sphere", radius=0.42, y=0.46)
    mesh("bowl_lid", shape="box", width=1.2, height=0.6, depth=1.2, y=0.9)
shot("drop03", name="Drop 03", camera=cam, fps=24, start=0, end=5)
'''
NUMBERS: dict = {"scrub": {}}
MOMENTS = (6, 12, 60)           # frames of the three fall pictures


def changes(doc):
    return len(doc.history.changes)


def of_type(doc, t):
    return [i["id"] for i in doc.items() if i.get("type") == t]


def find_class(root, name):
    """The first visible item under `root` whose QML type is `name` (the kit's ruler has no objectName)."""
    stack = [root]
    while stack:
        it = stack.pop()
        if it.isVisible() and it.metaObject().className().startswith(name):
            return it
        stack += it.childItems()
    return None


def row_of(w, item_id):
    return w.item(f"sceneRow:{item_id}")


def right_click_row(w, item_id):
    row = row_of(w, item_id)
    if row is None:
        return
    w.right_click(W.centre(row))


def snap(w, name):
    W.pump(30, lambda: w.s.ready(), f"{name}: the picture")
    W.pump(0.4)
    path = OUT / f"sim25-{name}.png"
    w.win.grabWindow().save(str(path))           # the window only, never the screen
    NUMBERS.setdefault("pictures", {})[name] = str(path)


def ruler_x(ruler, frame, fps, frames):
    """The window x of `frame` on the ruler (seconds across its width; the last 3 px are the end)."""
    p0 = ruler.mapToScene(QPointF(0, ruler.height() / 2))
    dur = ruler.property("duration") or frames / fps
    return QPoint(round(p0.x() + (frame / fps) / dur * (ruler.width() - 3)), round(p0.y()))


def scrub(w, frames, fps):
    """A real press-drag-release along the ruler over every 2nd frame: per move the GUI thread's ms, and the time from the
    move to the next picture the viewport shows (the engine reading the stored result for that frame)."""
    ruler = find_class(w.win.contentItem(), "TimeRuler")
    W.check(ruler is not None, "the timeline's ruler is on screen")
    if ruler is None:
        return
    v, gui, pic = w.v, [], []
    at = ruler_x(ruler, 0, fps, frames)
    QTest.mouseMove(w.win, at)
    QTest.mousePress(w.win, Qt.LeftButton, Qt.NoModifier, at)
    prof = None
    if os.environ.get("SIM25_PROFILE"):
        import cProfile
        prof = cProfile.Profile()
        prof.enable()
    for f in range(2, frames, 2):
        serial, t0 = v.serial, time.perf_counter()
        c0 = W.gui_cycles_ms()
        QTest.mouseMove(w.win, ruler_x(ruler, f, fps, frames))
        W.pump(0)
        gui.append(W.gui_cycles_ms() - c0)
        if W.pump(2, lambda: v.serial != serial):
            pic.append((time.perf_counter() - t0) * 1000)
        else:
            W.FAILS.pop()                       # a move inside the same frame shows no new picture: not a failure
    if prof is not None:
        import io
        import pstats
        prof.disable()
        out = io.StringIO()
        pstats.Stats(prof, stream=out).sort_stats("cumulative").print_stats(40)
        (OUT / "sim25-scrub-profile.txt").write_text(out.getvalue(), encoding="utf-8")
    QTest.mouseRelease(w.win, Qt.LeftButton, Qt.NoModifier, ruler_x(ruler, frames - 1, fps, frames))
    W.pump(0.3)

    def stats(xs):
        xs = sorted(xs)
        return {"n": len(xs), "median": round(xs[len(xs) // 2], 2), "p90": round(xs[int(len(xs) * 0.9)], 2),
                "max": round(xs[-1], 2)} if xs else {"n": 0}
    NUMBERS["scrub"] = {"guiMsPerMove": stats(gui), "moveToPictureMs": stats(pic)}
    W.check(len(pic) > frames // 4, f"scrubbing shows new pictures ({len(pic)} for {len(gui)} moves)")
    print("scrub:", NUMBERS["scrub"], flush=True)


def go_to(w, frame, fps, frames):
    """A real click on the ruler at `frame` (the playhead jumps there)."""
    ruler = find_class(w.win.contentItem(), "TimeRuler")
    if ruler is not None:
        QTest.mouseClick(w.win, Qt.LeftButton, Qt.NoModifier, ruler_x(ruler, frame, fps, frames))
        W.pump(5, lambda: abs(w.b.frame - frame) <= 1, f"the playhead at frame {frame}")


def simulate_click(w, timeout=180):
    """A click on the row's Simulate; waits for the job to land. Returns the states seen and a filling picture taken."""
    sim, seen = w.b.sim, []
    btn = w.item("simRun")
    if btn is None:
        return seen
    t0 = time.perf_counter()
    W.click(w.win, btn)
    caught = False
    end = time.perf_counter() + timeout
    while time.perf_counter() < end:
        W.pump(0.01)
        if not seen or seen[-1] != sim.state:
            seen.append(sim.state)
        if sim.state == "running" and 0.15 < sim.filled < 0.85 and not caught:
            caught = True
            w.win.grabWindow().save(str(OUT / "sim25-3-filling.png"))
            NUMBERS.setdefault("pictures", {})["3-filling"] = str(OUT / "sim25-3-filling.png")
        if sim._thread is not None and not sim.running() and sim.state != "running":
            break
    NUMBERS.setdefault("simulateMs", []).append(round((time.perf_counter() - t0) * 1000))
    W.pump(0.5)
    return seen


def shot_of(doc):
    return next(s for s in doc.data["shots"] if s["id"] == "drop03")


def stylize(w, doc, buds):
    """26a: Timing On 2s by real clicks in the Scene panel, read back as 2-frame holds; Turn into keys by a real click; a
    nudged key survives Simulate again."""
    b, sim = w.b, w.b.sim
    for _ in range(4):                                 # Esc steps back until nothing is selected: the Scene panel
        if b.selected == "":
            break
        QTest.keyClick(w.win, Qt.Key_Escape)
        W.pump(0.3)
    W.check(b.selected == "", f"nothing selected: the Scene panel ({b.selected!r})")
    row = w.item("row:simTiming")
    field = CW.field_of(row) if row is not None else None
    if field is not None:
        W.click(w.win, field)
        W.pump(3, lambda: W.find(w.win.contentItem(), "choiceList") is not None, "the Timing list")
        lst = W.find(w.win.contentItem(), "choiceList")
        entry = CP.find_text(lst, "On 2s") if lst is not None else None
        W.check(entry is not None, "the Timing list offers On 2s")
        if entry is not None:
            n = changes(doc)
            W.click(w.win, entry)
            W.pump(3, lambda: shot_of(doc).get("simTiming") == "2s", "Timing On 2s")
            W.check(changes(doc) == n + 1, f"Timing: one undo step ({n} -> {changes(doc)})")
    W.check(sim.state == "stored", f"Timing doesn't make the result out of date ({sim.state!r})")
    scene = b.scene()                                  # read only: the result as the viewport gets it
    nodes = {n["id"]: n for n in scene["items"]}
    W.check((nodes.get(buds, {}).get("sim") or {}).get("step") == 2, f"the buds' result is read on 2s ({nodes.get(buds, {}).get('sim')})")
    ys = (nodes.get("ball", {}).get("anim") or {}).get("y") or []
    held = len(ys) >= 4 and all(ys[i] == ys[i + 1] for i in range(0, len(ys) - 1, 2))
    W.check(held, f"the ball holds each pose 2 frames ({[round(y, 3) for y in ys[:6]]})")
    snap(w, "5d-on-2s")

    btn = w.item("sceneSimKeys")
    if btn is not None:
        n = changes(doc)
        W.click(w.win, btn)
        W.pump(5, lambda: doc.item("ball").get("simulate") == "off", "the ball Off after Turn into keys")
        W.check(changes(doc) == n + 1, f"Turn into keys: one undo step ({n} -> {changes(doc)})")
        keys = [k for k in doc.item("ball").get("keys", []) if k.get("prop") == "y"]
        W.check(len(keys) > 1, f"the ball has y keys ({len(keys)})")
        W.check(doc.item(buds).get("simulate") == "falls", "the buds (a copies item) keep simulating")
        snap(w, "5e-keys")
        if keys:
            last = max(keys, key=lambda k: k["t"])
            nudged = round(last["v"] + 0.05, 6)
            doc.apply([{"op": "key.set", "target": [last["id"]], "args": {"v": nudged}}], b.who, label="Nudge the ball")
            W.pump(1.0)
            if sim.canRun:
                simulate_click(w)
            W.check(sim.state == "stored", f"simulated again ({sim.state!r}: {sim.label!r})")
            now = next((k["v"] for k in doc.item("ball").get("keys", []) if k["id"] == last["id"]), None)
            W.check(now == nudged, f"the nudge survives a re-run ({nudged} -> {now})")
            W.check(doc.item("ball").get("simulate") == "off", "the ball stays Off")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-sim25walk-"))
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("drop03.py", run_source(SCENE, "drop03.py"))
    doc.save()
    screen = app3d.Screen(SIZE)
    try:
        screen.show(doc, shot_id="drop03", autosave=True)
        w = CW.Walk(screen, OUT)
        b, sim = w.b, screen.bridge.sim
        W.pump(90, screen.ready, "the first picture")
        info = b.shot_info()
        fps, frames = info["fps"], info["end"] - info["start"] + 1
        W.check(not sim.shown and W.find(w.win.contentItem(), "simRun") is None, "no Simulate row before anything is a body")

        # 1. the bowl stays still
        n0 = changes(doc)
        right_click_row(w, "bowl")
        W.check("menu:Simulate" in w.entries(), f"the bowl's menu has Simulate ({w.entries()})")
        w.choose("menu:Simulate", "sim:still")
        W.pump(5, lambda: doc.item("bowl").get("simulate") == "still", "the bowl: Stays still")
        W.check(changes(doc) == n0 + 1, f"Simulate › Stays still: one undo step ({n0} -> {changes(doc)})")
        W.check(w.item("simBadge:bowl") is not None, "the bowl's row has the body badge")
        snap(w, "1-bowl-still")
        right_click_row(w, "ball")       # a plain item that falls too (Turn into keys gives it keys, 26a); its row is
        w.choose("menu:Simulate", "sim:falls")      # last, in sight while the buds are one row
        W.pump(5, lambda: doc.item("ball").get("simulate") == "falls", "the ball: Falls")

        # 2. twelve buds in a line, falling
        right_click_row(w, "bud")
        w.choose("menu:Make copies", "copies:make:line")
        W.pump(5, lambda: of_type(doc, "copies"), "the copies item")
        buds = (of_type(doc, "copies") or ["copies_1"])[0]
        W.pump(5, lambda: b.selected == buds, "the copies item selected")
        w.type_count(12)
        w.type_into("spacingX", SPACING)
        W.check(doc.item(buds)["count"] == 12, f"Count 12 ({doc.item(buds)['count']})")
        n1 = changes(doc)
        right_click_row(w, buds)
        w.choose("menu:Simulate", "sim:falls")
        W.pump(5, lambda: doc.item(buds).get("simulate") == "falls", "the buds: Falls")
        W.check(changes(doc) == n1 + 1, f"Simulate › Falls: one undo step ({n1} -> {changes(doc)})")
        W.pump(3, lambda: sim.shown, "the Simulate row")
        W.check(sim.state == "not computed" and w.item("simRun") is not None,
                f"the row: Not computed with Simulate ({sim.state!r}, {sim.label!r})")
        W.check(w.item(f"simBadge:{buds}") is not None, "the buds' row has the falling-arrow badge")
        snap(w, "2-not-computed")

        # 3. Simulate: the bar fills, then Stored
        n2 = changes(doc)
        seen = simulate_click(w)
        NUMBERS["statesSeen"] = seen
        W.check("running" in seen, f"the job ran off the GUI thread with the row filling ({seen})")
        W.check(sim.state == "stored", f"Stored ({sim.state!r}: {sim.label!r})")
        W.check(sim.label == f"Stored · {frames} frames", f"the row reads Stored · {frames} frames ({sim.label!r})")
        W.check(changes(doc) == n2 + 1, f"Simulate recorded in one undo step ({n2} -> {changes(doc)})")
        key = next(s for s in doc.data["shots"] if s["id"] == "drop03").get("simKey", "")
        W.check(bool(key), "the shot's stored result key is set")
        snap(w, "4-stored")

        # 4. scrub the stored result; three moments of the fall
        scrub(w, frames, fps)
        for name, f in zip("abc", MOMENTS):
            go_to(w, f, fps, frames)
            snap(w, f"5-fall-{name}-f{f}")

        # 4b. (26a) Timing On 2s, Turn into keys, a nudge that survives a re-run
        stylize(w, doc, buds)
        key = next(s for s in doc.data["shots"] if s["id"] == "drop03").get("simKey", "")   # re-simulated in 4b

        # 5. the bowl moved: out of date, striped; the old result still shown
        go_to(w, MOMENTS[1], fps, frames)
        W.click(w.win, row_of(w, "bowl"))
        W.pump(5, lambda: b.selected == "bowl", "the bowl selected")
        w.type_into("x", 0.06)
        W.pump(3, lambda: sim.state == "out of date", "Out of date")
        W.check(sim.state == "out of date", f"moving the bowl: Out of date ({sim.state!r})")
        W.check(w.item("simStripes") is not None, "the bar is striped")
        W.check(next(s for s in doc.data["shots"] if s["id"] == "drop03").get("simKey") == key,
                "the viewport keeps the old result (the shot's key unchanged)")
        snap(w, "6-out-of-date")

        # 6. a bud started inside the bowl: the core's failure, loud, in the row
        W.click(w.win, row_of(w, buds))
        W.pump(5, lambda: b.selected == buds, "the buds selected")
        w.type_into("y", 0.05)
        W.pump(3, lambda: sim.canRun, "Simulate offered again")
        seen = simulate_click(w)
        W.check(sim.state == "failed", f"a bud inside the bowl fails ({sim.state!r}: {sim.label!r})")
        name = outline.label_of(doc.item(buds))
        W.check("frame" in sim.failure and name in sim.failure and not sim.failure.startswith("Error"),
                f"the failure names the body by its name and the frame, without the Error prefix ({sim.failure!r})")
        NUMBERS["failure"] = sim.failure
        snap(w, "7-failed")
    finally:
        NUMBERS["fails"] = list(W.FAILS)
        (OUT / "sim25_walk.json").write_text(json.dumps(NUMBERS, indent=2), encoding="utf-8")
        screen.close()
        app.processEvents()
        shutil.rmtree(project, ignore_errors=True)
    print("FAILS:" if W.FAILS else "ALL PASSED", *W.FAILS, sep="\n  ")
    sys.exit(1 if W.FAILS else 0)


if __name__ == "__main__":
    main()
