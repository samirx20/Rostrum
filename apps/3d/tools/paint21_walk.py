# Brief 21 walk (painting, part 2): tried by real input in the real window (a background window at 1646 x 900, never
# focused): real mouse and keys on visible controls found by objectName or their words; the document is only read, to
# CHECK. A scratch project: a case with its lid on a plinth, three walls behind, the shot "Hero 01", and a 2D item
# "Poster" with a pictures render (written here as 2D would: renders/poster/v001). Then:
#   1. a click on the case, B: Paint; "From the view" and the coverage tint (▨) clicked: "Seen by Hero 01: 0 % painted"
#   2. one drag From the view across the case and the lid: one undo step, a stroke (as drawn) on both; the percent
#      rises; GUI thread time per pointer move (cycles) ................................... "1-view-stroke-coverage"
#   3. B leaves; the three walls Ctrl+clicked in the scene list; a right-click on the back wall › Project a picture from
#      Hero 01… › Poster: a projected layer on each wall .................................. "2-projected-hero"
#   4. the view turned by a right drag: the poster stays on the walls, the case's shadow in it shows depth
#      ..................................................................................... "3-projected-turned"
#   5. the poster repainted and rendered again in 2D (v002 written): the walls follow by themselves "4-repainted-2d"
# Every check and the numbers go to paint21_walk.json. The lead runs it:
#   heavy.ps1 run "hem: 3d-21 walk" gpu <venv python> apps\3d\tools\paint21_walk.py <out folder>
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-21\walk")
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_walk as W  # noqa: E402  (puts this checkout's code first; its real-input helpers)
import clay_paint_walk as CP  # noqa: E402

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document, Who, project  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d.gizmo import View  # noqa: E402

AGENT = Who.agent("paint21-walk") if hasattr(Who, "agent") else Who.person()
SCENE = '''
shell = material("shell", baseColor="#2c3a4a", roughness=0.45)
top = material("top", baseColor="#3a4c5e", roughness=0.4)
wall = material("wall", baseColor="#b9b4aa", roughness=0.85)
floor = material("floor", baseColor="#6a6d72", roughness=0.8)
mesh("plinth", shape="box", width=1.2, height=0.02, depth=0.9, y=-0.01, z=-0.1, material=floor)
mesh("case", name="Case", shape="box", width=0.24, height=0.08, depth=0.16, y=0.04, material=shell)
mesh("lid", name="Lid", shape="box", width=0.25, height=0.03, depth=0.17, y=0.095, material=top)
mesh("wall_back", name="Wall back", shape="plane", width=0.9, depth=0.5, y=0.25, z=-0.45, rx=90, material=wall)
mesh("wall_left", name="Wall left", shape="plane", width=0.5, depth=0.6, x=-0.45, y=0.25, z=-0.15, rz=-90, material=wall)
mesh("wall_right", name="Wall right", shape="plane", width=0.5, depth=0.6, x=0.45, y=0.25, z=-0.15, rz=90, material=wall)
light("key", kind="rect", width=0.6, height=0.4, intensity=25, x=-0.4, y=0.7, z=0.6).aim((0, 0.05, 0))
light("sky", kind="dome", color="#c8d2e0", intensity=0.6)
cam = camera("cam", focalLength=28, y=0.32, z=0.78).aim((0, 0.12, -0.12))
shot("hero", name="Hero 01", camera=cam, fps=24, start=0, end=2)
'''
REPORT = CP.REPORT
chk, step, settle, shot = CP.chk, CP.step, CP.settle, CP.shot


def poster(folder: Path, version_words: str, hue: tuple):
    """A 2D render of the poster item as Rostrum2D writes one (pictures, PNG frames)."""
    from PIL import Image, ImageDraw
    part = project.begin_render(folder, "poster")
    im = Image.new("RGB", (960, 540), hue)
    d = ImageDraw.Draw(im)
    for i in range(0, 960, 120):
        d.rectangle([i, 0, i + 60, 540], fill=(250, 240, 220))
    d.ellipse([330, 120, 630, 420], fill=(220, 60, 50) if version_words == "v1" else (40, 170, 90))
    d.text((40, 480), f"poster {version_words}", fill=(0, 0, 0))
    im.save(part / "poster_main.1001.png")
    project.finish_render(part, {"kind": "pictures", "frames": {"first": 1001, "last": 1001, "fps": "24/1", "start": 0.0}})


def on_screen(screen, item_id, vp, local=(0.0, 0.0, 0.0)):
    """The window point of `local` (the item's own space) in the viewport."""
    v, frame = screen.bridge.viewport, screen.bridge.frame
    scene, cam = v.sent()
    view = View.of(cam, scene, frame, cam["width"], cam["height"])
    from rostrum3d import aim, through
    world = through.find_item(scene, item_id, frame)[0]
    x, y, _ = view.project(aim.point(world, list(local)))
    to_win = 1.0 / (v._scale * vp.window().devicePixelRatio())
    top = vp.mapToScene(QPointF(0, 0))
    return QPointF(top.x() + x * to_win, top.y() + y * to_win)


def percent(line: str):
    m = re.search(r"(\d+) % painted", line or "")
    return int(m.group(1)) if m else None


def view_strokes(doc, item_id):
    it = doc.item(item_id)
    return [s for p in it.get("paints", []) for s in p.get("strokes", []) if s.get("viewPoints")]


def diff_share(a, b, box):
    from PIL import ImageChops
    ca, cb = a.crop(box), b.crop(box)
    d = ImageChops.difference(ca, cb).convert("L").point(lambda v: 255 if v > 24 else 0)
    return sum(1 for v in d.getdata() if v) / max(1, d.width * d.height)


def grab(win):
    from PIL import Image
    img = win.grabWindow()
    path = OUT / "_tmp.png"
    img.save(str(path))
    with Image.open(path) as im:
        return im.convert("RGB").copy()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    CP.OUT = OUT
    folder = Path(tempfile.mkdtemp(prefix="rostrum-paint21walk-"))
    app = qt_app()  # noqa: F841
    doc = Document.new(KIND, folder=folder, item="scene")
    doc.run_script("scene.py", run_source(SCENE, "scene.py"))
    doc.save()
    pj = folder / "project.json"
    data = json.loads(pj.read_text(encoding="utf-8")) if pj.is_file() else {"items": []}
    data.setdefault("items", []).append({"id": "poster", "kind": "2d", "name": "Poster"})
    pj.write_text(json.dumps(data, indent=2), encoding="utf-8")
    poster(folder, "v1", (40, 60, 120))
    screen = W.app3d.Screen(W.SIZE)
    try:
        screen.show(doc, autosave=True)
        win, v, b = screen.win, screen.bridge.viewport, screen.bridge
        W.pump(90, screen.ready, "the first picture")
        vp = W.find(win.contentItem(), "viewport3d")
        D = b.doc
        settle(v, time.perf_counter(), what="the first settled picture")

        # 1. Paint on the case, From the view, the tint
        step("1 paint from the view")
        QTest.keyClick(win, Qt.Key_V)
        case_mid = on_screen(screen, "case", vp, (0.0, 0.0, 0.08))          # the case's front face
        at = case_mid.toPoint()
        QTest.mouseMove(win, at)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
        W.pump(10, lambda: b.selected == "case", "the case selected by the click")
        chk(b.selected == "case", f"a click on the case selects it ({b.selected})")
        QTest.keyClick(win, Qt.Key_B)
        W.pump(3, lambda: v.paint.on, "Paint on")
        W.pump(0.5)
        word = CP.find_text(win.contentItem(), "From the view")
        chk(word is not None, "the From the view choice is on screen")
        if word is not None:
            W.click(win, word)
        W.pump(2, lambda: v.paint.where == "view", "From the view picked")
        chk(v.paint.where == "view", f"From the view picked by a click ({v.paint.where})")
        tint = W.find(win.contentItem(), "paintCoverage")
        chk(tint is not None, "the coverage tint button is on screen")
        if tint is not None:
            W.click(win, tint)
        W.pump(40, lambda: percent(v.paint.coverage.line) is not None and "tinting" not in v.paint.coverage.line, "the coverage line")
        line0 = v.paint.coverage.line
        REPORT["coverageBefore"] = line0
        chk(percent(line0) is not None and "Hero 01" in line0, f"the Layers header says what Hero 01 sees ({line0!r})")
        settle(v, time.perf_counter(), what="the tinted picture")
        shot(win, v, "0-tint-before")

        # 2. one drag across the case and the lid
        step("2 view stroke across case and lid")
        a = on_screen(screen, "case", vp, (-0.10, -0.01, 0.08))
        c = on_screen(screen, "lid", vp, (0.10, 0.015, 0.0))
        pts = CP.line((a.x(), a.y()), (c.x(), c.y()), n=60)
        n0 = len(D.history.changes)
        QTest.mouseMove(win, pts[0])
        W.pump(0.25)
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, pts[0])
        per_move = []
        for p in pts[1:]:
            c0 = W.gui_cycles_ms()
            QTest.mouseMove(win, p)
            W.pump(0)
            per_move.append(W.gui_cycles_ms() - c0)
            W.pump(0.012)
        t_up = time.perf_counter()
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, pts[-1])
        W.pump(30, lambda: len(D.history.changes) > n0 or v.status.startswith("Error"), "the stroke's change")
        REPORT["timesMs"]["view-stroke-doc-change"] = round((time.perf_counter() - t_up) * 1000)
        ms = settle(v, t_up, what="the view stroke's picture")
        REPORT["timesMs"]["view-stroke-picture-settled"] = round(ms)
        REPORT["perMoveGuiMsInOrder"] = [round(x, 2) for x in per_move]
        per_move.sort()
        REPORT["perMoveGuiMs"] = {"median": round(per_move[len(per_move) // 2], 2), "max": round(per_move[-1], 2),
                                  "moves": len(per_move)}
        chk(per_move[-1] < 16.0, f"each pointer move within the 16 ms budget on the window's thread "
                                 f"(median {per_move[len(per_move) // 2]:.2f} ms, max {per_move[-1]:.2f} ms)")
        chk(not v.status.startswith("Error"), f"no error after the stroke ({v.status or '-'})")
        chk(len(D.history.changes) == n0 + 1, f"the stroke is one undo step ({n0} -> {len(D.history.changes)})")
        on_case, on_lid = view_strokes(D, "case"), view_strokes(D, "lid")
        chk(len(on_case) == 1 and len(on_lid) == 1, f"the stroke is on the case and on the lid ({len(on_case)}, {len(on_lid)})")
        if on_case and on_lid:
            chk(on_case[0]["viewPoints"] == on_lid[0]["viewPoints"], "both keep it as drawn (the same points)")
        W.pump(40, lambda: (percent(v.paint.coverage.line) or 0) > (percent(line0) or 0) and "tinting" not in v.paint.coverage.line, "the percent to rise")
        line1 = v.paint.coverage.line
        REPORT["coverageAfter"] = line1
        chk((percent(line1) or 0) > (percent(line0) or 0), f"the percent changes as you paint ({line0!r} -> {line1!r})")
        settle(v, time.perf_counter(), what="the tint after the stroke")
        shot(win, v, "1-view-stroke-coverage")

        # 3. project the poster onto the three walls
        step("3 project a picture")
        QTest.keyClick(win, Qt.Key_B)
        W.pump(3, lambda: not v.paint.on, "Paint off")
        names = ["Wall back", "Wall left", "Wall right"]
        for i, name in enumerate(names):
            row = CP.find_text(win.contentItem(), name)
            chk(row is not None, f"the scene list shows {name}")
            if row is not None:
                p = row.mapToScene(QPointF(row.width() / 2, row.height() / 2)).toPoint()
                QTest.mouseClick(win, Qt.LeftButton, Qt.ControlModifier if i else Qt.NoModifier, p)
                W.pump(0.3)
        W.pump(3, lambda: set(b.selection) == {"wall_back", "wall_left", "wall_right"}, "the three walls selected")
        chk(set(b.selection) == {"wall_back", "wall_left", "wall_right"}, f"the three walls are selected ({b.selection})")
        back = on_screen(screen, "wall_back", vp, (0.38, 0.0, -0.18)).toPoint()     # high up on the back wall
        QTest.mouseMove(win, back)
        QTest.mouseClick(win, Qt.RightButton, Qt.NoModifier, back)
        W.pump(10, lambda: W.find(win.contentItem(), "menu:paint:project") is not None, "the right-click menu")
        W.pump(0.3)
        entry = W.find(win.contentItem(), "menu:paint:project")
        chk(entry is not None, "the right-click menu offers Project a picture from Hero 01…")
        if entry is not None:
            chk("Hero 01" in (entry.property("text") or "Hero 01"), "named after the shot")
            W.click(win, entry)
        W.pump(5, lambda: W.find(win.contentItem(), "menu:2d:poster") is not None, "the picture menu")
        W.pump(0.3)
        pick = W.find(win.contentItem(), "menu:2d:poster")
        chk(pick is not None, "the picture menu lists the Poster (2D)")
        n0 = len(D.history.changes)
        t0 = time.perf_counter()
        if pick is not None:
            W.click(win, pick)
        W.pump(30, lambda: len(D.history.changes) > n0 or b.status.startswith("Error"), "the projection's change")
        layers = {w: [p for p in D.item(w).get("paints", []) if p.get("projectSource") == "2d:poster"]
                  for w in ("wall_back", "wall_left", "wall_right")}
        chk(all(len(x) == 1 for x in layers.values()), f"a projected layer on each wall ({ {k: len(x) for k, x in layers.items()} })")
        chk(len(D.history.changes) == n0 + 1, "one undo step")
        QTest.keyClick(win, Qt.Key_Escape)
        REPORT["timesMs"]["projection-picture-settled"] = round(settle(v, t0, what="the projected picture"))
        shot(win, v, "2-projected-hero")
        hero = grab(win)

        # 4. turn the view: the picture stays on the walls (depth)
        step("4 view turned")
        mid = vp.mapToScene(QPointF(vp.width() / 2, vp.height() / 2)).toPoint()
        QTest.mouseMove(win, mid)
        QTest.mousePress(win, Qt.RightButton, Qt.NoModifier, mid)
        for k in range(1, 25):
            QTest.mouseMove(win, QPoint(mid.x() + 9 * k, mid.y() - 2 * k))
            W.pump(0.015)
        QTest.mouseRelease(win, Qt.RightButton, Qt.NoModifier, QPoint(mid.x() + 216, mid.y() - 48))
        settle(v, time.perf_counter(), what="the turned view")
        shot(win, v, "3-projected-turned")
        chk(v.mode == "free", f"the view turned (free camera: {v.mode})")

        # 5. repainted in 2D
        step("5 repainted in 2D")
        before = grab(win)
        poster(folder, "v2", (120, 40, 60))
        t0 = time.perf_counter()
        box = tuple(round(c * before.width / win.width()) for c in (vp.mapToScene(QPointF(0, 0)).x(),
                    vp.mapToScene(QPointF(0, 0)).y(), vp.mapToScene(QPointF(vp.width(), vp.height())).x(),
                    vp.mapToScene(QPointF(vp.width(), vp.height())).y()))
        changed = W.pump(20, lambda: diff_share(before, grab(win), box) > 0.03, "the walls to follow the new 2D render")
        REPORT["timesMs"]["repaint-2d-followed"] = round((time.perf_counter() - t0) * 1000)
        chk(changed, "repainting the poster in 2D updates the walls by itself")
        settle(v, time.perf_counter(), what="the repainted picture")
        shot(win, v, "4-repainted-2d")
        REPORT["heroVsTurned"] = round(diff_share(hero, before, box), 3)
    finally:
        (OUT / "_tmp.png").unlink(missing_ok=True)
        REPORT["fails"] = list(W.FAILS)
        (OUT / "paint21_walk.json").write_text(json.dumps(REPORT, indent=2), encoding="utf-8")
        screen.close() if hasattr(screen, "close") else None
    print("FAILS:" if W.FAILS else "ALL PASSED", *W.FAILS, sep="\n  ")
    sys.exit(1 if W.FAILS else 0)


if __name__ == "__main__":
    main()
