# Clay draw walk (CL3): Draw, Spin's neighbour and Turn into clay tried by real input in the real window (behind the
# person's work, never focused), the first minutes of 3d-simplicity SPEC § 1. A scratch project with only a ground, two
# lights and the shot camera; Q (the real key): Draw is chosen. Then real drags, each timed from the release until the
# document changed and until the picture settled, a picture after each:
#   1. the body: a pear outline over the ground, about half the viewport tall -> a new clay, selected;
#   2. an arm: the pointer resting on the body first (it is outlined: the picture "arm-hover"), then an outline starting
#      on the body's side -> one more step on the same clay (Mirror makes the other arm);
#   3. 4. two feet: small ovals starting on the body's bottom -> a step each on the same clay;
#   5. V, the Shapes rail's Box placed on the ground by a click, Q, the "Turn into clay" tile -> a clay copy, selected,
#      the box hidden; then a Carve stroke across it (one more step).
# Each drag must be exactly one undo step. Pictures and the numbers (clay_draw_walk.json) go to the out folder. Needs the
# core built with CL3's shapes; the lead runs it:
#   heavy.ps1 run "sam: clay draw walk" gpu <venv python> apps\3d\tools\clay_draw_walk.py --out <folder>
# Exit 0 = every check passed; else the failed checks are printed and it exits 1.
import argparse
import ctypes as ct
import json
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_walk as W  # noqa: E402  (puts this checkout's code first; its real-input helpers)

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402

SCENE = '''
floor = material("floor", baseColor="#3a3d42", roughness=0.8)
mesh("ground", shape="plane", width=6, depth=6, material=floor)
light("key", kind="rect", width=1.2, height=0.8, intensity=6, temperature=5200, x=1.4, y=1.6, z=1.2).aim((0, 0.3, 0))
light("sky", kind="dome", color="#9fb2cc", intensity=0.25)
cam = camera("cam", focalLength=35, y=0.6, z=2.4).aim((0, 0.3, 0))
shot("s", camera=cam, fps=24, start=0, end=2)
'''


def clays(doc):
    out, stack = [], list(doc.data.get("items", []))
    while stack:
        it = stack.pop()
        out += [it["id"]] if it.get("type") == "clay" else []
        stack += it.get("children", [])
    return out


def loop(c, a, b, n=36, start=0.0, tilt=0.0):
    """An ellipse of half-axes a (along `tilt` radians) and b, centre c (window px), from angle `start`, closed."""
    d, p = (math.cos(tilt), math.sin(tilt)), (-math.sin(tilt), math.cos(tilt))
    pts = []
    for i in range(n + 1):
        t = start + 2 * math.pi * i / n
        u, v = a * math.cos(t), b * math.sin(t)
        pts.append(QPoint(round(c[0] + u * d[0] + v * p[0]), round(c[1] + u * d[1] + v * p[1])))
    return pts


def pear(cx, cy, rx, ry, n=48):
    """A pear standing up: wide at the bottom, narrower at the top, from its right side."""
    return [QPoint(round(cx + rx * (0.75 + 0.25 * math.sin(t)) * math.cos(t)), round(cy + ry * math.sin(t)))
            for t in (2 * math.pi * i / n for i in range(n + 1))]


def settled(v):
    return v._r.idle() and not v._next.isActive()


def draw(screen, win, name, pts, out, rest=0.3):
    """One real outline drag: the pointer rests on its start (`rest` s: the clay under it outlined), presses, moves
    through `pts`, lets go. Timed from the release to the document's change and to the settled picture."""
    doc, v = screen.bridge.doc, screen.bridge.viewport
    n0, before = len(doc.history.changes), set(clays(doc))
    QTest.mouseMove(win, pts[0])
    W.pump(rest)
    hover = v.clay.drawObj.joining
    QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, pts[0])
    t_draw = time.perf_counter()
    for p in pts[1:]:
        QTest.mouseMove(win, p)
        W.pump(0.008)
    chip = v.clay.drawObj.chip
    draw_ms = (time.perf_counter() - t_draw) * 1000
    t0 = time.perf_counter()
    QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, pts[-1])
    W.pump(20, lambda: len(doc.history.changes) > n0 or v.status.startswith("Error"), f"{name}: the change")
    changed_ms = (time.perf_counter() - t0) * 1000
    W.pump(30, lambda: settled(v), f"{name}: the picture")
    W.pump(0.1)
    shown_ms = (time.perf_counter() - t0) * 1000
    W.check(not v.status.startswith("Error"), f"{name}: no error ({v.status or '-'})")
    W.check(len(doc.history.changes) == n0 + 1, f"{name}: one undo step ({n0} -> {len(doc.history.changes)})")
    slug = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
    win.grabWindow().save(str(out / f"clay-draw-{slug}.png"))
    return {"name": name, "points": len(pts), "chip": chip, "hoverJoins": hover, "drawMs": round(draw_ms),
            "changedMs": round(changed_ms), "shownMs": round(shown_ms),
            "newClays": [c for c in clays(doc) if c not in before], "selected": screen.bridge.selected}


def steps_of(doc, clay_id):
    return len(doc.item(clay_id).get("steps", [])) if clay_id and doc.has(clay_id) else 0


def turn_into_clay(screen, win, vp_item, out, report):
    """V, Shapes › Box clicked on the ground left of the body, Q, Turn into clay, then Carve across the copy."""
    doc, v, b = screen.bridge.doc, screen.bridge.viewport, screen.bridge
    QTest.keyClick(win, Qt.Key_V)
    W.pump(0.3)
    rail = W.find(win.contentItem(), "rail_shapes")
    W.check(rail is not None, "the Shapes rail button is there")
    W.click(win, rail)
    box_tile = W.find(win.contentItem(), "fly_mesh:box")
    W.check(box_tile is not None, "the Box entry is in the Shapes flyout")
    if box_tile is None:
        return
    W.click(win, box_tile)
    at = vp_item.mapToScene(QPointF(vp_item.width() * 0.25, vp_item.height() * 0.8)).toPoint()
    QTest.mouseMove(win, at)
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
    W.pump(20, lambda: b.selected and doc.has(b.selected) and doc.item(b.selected).get("type") == "mesh", "the box")
    box = b.selected
    W.check(bool(box) and doc.item(box).get("shape") == "box", f"a click on the ground placed the box ({box})")
    W.pump(30, lambda: settled(v), "the box drawn")
    QTest.keyClick(win, Qt.Key_Q)
    W.pump(0.3)
    tile = W.find(win.contentItem(), "clayMakeTurn into clay")
    W.check(tile is not None, "with the box selected, the Clay panel shows Turn into clay")
    if tile is None:
        return
    before, n0, t0 = set(clays(doc)), len(doc.history.changes), time.perf_counter()
    W.click(win, tile)
    W.pump(20, lambda: len(doc.history.changes) > n0, "Turn into clay's change")
    W.pump(30, lambda: settled(v), "the clay copy drawn")
    ms = (time.perf_counter() - t0) * 1000
    new = [c for c in clays(doc) if c not in before]
    W.check(len(new) == 1 and b.selected == new[0], f"Turn into clay made one clay, selected ({new}, {b.selected})")
    W.check(doc.has(box) and doc.item(box).get("visible", True) is False, "the box is hidden, not deleted")
    W.check(len(doc.history.changes) == n0 + 1, "Turn into clay is one undo step")
    win.grabWindow().save(str(out / "clay-draw-turn-into-clay.png"))
    report["turnIntoClay"] = {"clay": new[0] if new else "", "ms": round(ms)}
    if not new:
        return
    W.pick_tile(win, v.clay, "Carve", "carve")
    centre, radius = W.clay_on_screen(screen, new[0], vp_item)
    scene = v.sent()[0]
    core = W.K32.OpenProcess(0x1000, False, W.core_pid(v, scene))
    report["carve"] = W.stroke(screen, win, "Carve on the turned box", "carve", centre, radius, Qt.NoModifier, core)
    W.K32.CloseHandle(ct.c_void_p(core))


def main():
    ap = argparse.ArgumentParser(description="The Clay tool's Draw and Turn into clay, by real input in the real window")
    ap.add_argument("--out", default=r"C:\Users\Sam\.rostrum\waves\results\3d-cl3")
    out = Path(ap.parse_args().out)
    W.OUT = out
    out.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-claydraw-"))
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("scene.py", run_source(SCENE, "scene.py"))
    doc.save()
    screen = W.app3d.Screen(W.SIZE)
    report = {"draws": []}
    try:
        screen.show(doc, autosave=True)
        win, v = screen.win, screen.bridge.viewport
        W.pump(60, screen.ready, "the first picture")
        vp_item = W.find(win.contentItem(), "viewport3d")
        QTest.keyClick(win, Qt.Key_Q)
        W.pump(0.3)
        W.check(v.clay.on and v.clay.tool == "draw", f"Q turns Clay on with Draw chosen ({v.clay.tool})")
        top = vp_item.mapToScene(QPointF(0, 0))
        w, h = vp_item.width(), vp_item.height()
        cx, cy, rx, ry = top.x() + 0.5 * w, top.y() + 0.6 * h, 0.12 * h, 0.25 * h

        body = draw(screen, win, "Body", pear(cx, cy, rx, ry), out, rest=0.1)
        report["draws"].append(body)
        clay = body["newClays"][0] if body["newClays"] else ""
        W.check(bool(clay) and body["selected"] == clay, f"the body is a new clay, selected ({body['newClays']})")
        W.check(body["chip"].endswith("cm") or body["chip"].endswith(" m"), f"the size chip while drawing ({body['chip']})")
        if clay:
            n = steps_of(doc, clay)
            sx, sy = cx + 0.45 * rx, cy - 0.2 * ry                       # on the body, near its right side
            arm = loop((sx + 0.09 * h, sy - 0.03 * h), 0.09 * h, 0.025 * h, start=math.pi, tilt=-0.3)
            rec = draw(screen, win, "Arm", [QPoint(round(sx), round(sy))] + arm, out)
            report["draws"].append(rec)
            W.check(rec["hoverJoins"] == clay, f"resting on the body before the arm outlines it ({rec['hoverJoins']})")
            W.check(steps_of(doc, clay) == n + 1 and not rec["newClays"], "the arm joins the body: one step on it")
            for side, name in ((-1, "Left foot"), (1, "Right foot")):
                n = steps_of(doc, clay)
                fx, fy = cx + side * 0.3 * rx, cy + 0.85 * ry
                foot = loop((cx + side * 0.45 * rx, cy + ry + 0.01 * h), 0.05 * h, 0.022 * h, start=-math.pi / 2)
                rec = draw(screen, win, name, [QPoint(round(fx), round(fy))] + foot, out)
                report["draws"].append(rec)
                W.check(steps_of(doc, clay) == n + 1 and not rec["newClays"], f"{name}: joins the body (one step)")
        turn_into_clay(screen, win, vp_item, out, report)
    except Exception as e:  # noqa: BLE001  a crash is a failed walk, said with its reason
        W.FAILS.append(f"the walk stopped: {type(e).__name__}: {e}")
    finally:
        report["fails"] = W.FAILS
        (out / "clay_draw_walk.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        screen.close()
        W.pump(1.0)
        shutil.rmtree(project, ignore_errors=True)
    print(f"{len(W.FAILS)} failed check(s); numbers and pictures in {out}")
    for f in W.FAILS:
        print("  " + f)
    app.quit()
    return 1 if W.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
