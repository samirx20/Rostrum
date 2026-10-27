# CL6 walk: a new project, a body, a mirrored eye, a touchpad turn + Make this the shot, a right-drag turn and a right
# click, by real input in the real window (behind the person's work, never focused; 1646 x 900).
#   1. new-project: the window as it opens on files_3d.blank (Shot 1 crumb, ground + Studio sky, nothing selected, Sky).
#   2. Clay (Q) Draw: a pear outline over the ground makes a body (Mirror on by default).
#   3. Shapes > Sphere from the rail, ONE click on the body's face off the middle: two spheres, one "(mirrored)" whose
#      `mirror` is the other.
#   4. A two-finger touchpad scroll (QWheelEvent with pixel steps and a scroll phase) turns the view (Free camera);
#      the visible "Make this the shot" button (takeShot) clicked: the shot camera moved, one undo step, back on the shot.
#   5. A right drag turns the view too; a right click without moving opens the menu; Esc.
# Pictures (the window's own pixels only) and cl6_walk.json go to the out folder. The lead runs it:
#   heavy.ps1 run "sam: cl6 walk" gpu <venv python> apps\3d\tools\cl6_walk.py <out folder>
# Exit 0 = every check passed; else the failed checks are printed and it exits 1.
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-cl6\walk")
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_draw_walk as D  # noqa: E402  (its helpers; puts this checkout's code first)
import clay_walk as W  # noqa: E402

from PySide6.QtCore import QCoreApplication, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d import files_3d  # noqa: E402

_VIEW = []
CLICK = tuple(float(x) for x in os.environ.get("CL6_CLICK", "0.5,-0.1").split(","))


def shot(win, name, report):
    W.pump(30, lambda: D.settled(_VIEW[0]), "the picture to settle")
    W.pump(0.3)
    path = OUT / f"{name}.png"
    win.grabWindow().save(str(path))
    report["pictures"][name] = str(path)


def all_items(item):
    yield item
    for c in item.childItems():
        yield from all_items(c)


def texts(root):
    return [str(c.property("text")) for c in all_items(root) if c.isVisible() and isinstance(c.property("text"), str) and c.property("text")]


def cameras(doc):
    out, stack = {}, list(doc.data.get("items", []))
    while stack:
        it = stack.pop()
        if it.get("type") == "camera":
            out[it["id"]] = json.dumps(it, sort_keys=True)
        stack += it.get("children", [])
    return out


def meshes(doc, shape):
    out, stack = [], list(doc.data.get("items", []))
    while stack:
        it = stack.pop()
        if it.get("type") == "mesh" and it.get("shape") == shape:
            out.append(it)
        stack += it.get("children", [])
    return out


def spy_mirrors(report):
    """Diagnosis only: record what the placing code asked `mirrors` and what it answered (nothing is changed)."""
    from screen3d import placing
    real = placing.mirrors

    def spy(clay, world, point, size):
        out = real(clay, world, point, size)
        report.setdefault("mirrorsCalls", []).append({"clay": None if clay is None else {k: clay.get(k) for k in ("id", "type", "symmetry")},
                                                      "world": world, "point": list(point), "size": size, "answer": out})
        return out
    placing.mirrors = spy


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-cl6-"))
    app = qt_app()
    doc = files_3d.blank(project)
    screen = W.app3d.Screen(W.SIZE)
    report = {"pictures": {}, "notes": []}
    try:
        screen.show(doc, autosave=True)
        win, v, b = screen.win, screen.bridge.viewport, screen.bridge
        _VIEW.append(v)
        spy_mirrors(report)
        W.pump(60, screen.ready, "the first picture")
        root = win.contentItem()
        vp = W.find(root, "viewport3d")
        top = vp.mapToScene(QPointF(0, 0))
        w, h = vp.width(), vp.height()
        QTest.mouseMove(win, QPoint(8, 8))
        W.pump(0.5)

        # 1. new project
        shot(win, "1-new-project", report)
        t = texts(root)
        report["texts"] = t[:80]
        W.check(any("Shot 1" in x for x in t), "the Shot 1 crumb is there")
        W.check(not b.selected, f"nothing is selected ({b.selected!r})")
        W.check(v.hasShot and v.mode == "shot", f"the view is on the shot camera ({v.mode})")
        pic = W.find(root, "scenePicture")
        W.check(pic is not None, "the Scene panel's Sky picture list is on screen (scenePicture)")
        W.check(any("Studio" in x for x in t), "the Sky picture reads Studio")
        W.check(len(meshes(b.doc, "plane")) >= 1, "a ground exists")

        # 2. a body
        QTest.keyClick(win, Qt.Key_Q)
        W.pump(0.3)
        W.check(v.clay.on and v.clay.tool == "draw", f"Q: Clay on, Draw ({v.clay.tool})")
        cx, cy, rx, ry = top.x() + 0.5 * w, top.y() + 0.6 * h, 0.2 * h, 0.25 * h
        body = D.draw(screen, win, "Body", D.pear(cx, cy, rx, ry), OUT, rest=0.1)
        clay = body["newClays"][0] if body["newClays"] else ""
        W.check(bool(clay), f"a body was drawn ({body['newClays']})")
        if not clay:
            raise RuntimeError("no body to test with")
        report["clayItem"] = {k: v_ for k, v_ in b.doc.item(clay).items() if k != "steps"}
        report["clayItem"]["nSteps"] = len(b.doc.item(clay).get("steps", []))
        QTest.mouseMove(win, QPoint(8, 8))
        shot(win, "2-body", report)

        # 3. a sphere on the body's face, off the middle
        rail = W.find(root, "rail_shapes")
        W.check(rail is not None, "the Shapes rail button is there")
        W.click(win, rail)
        tile = W.find(root, "fly_mesh:sphere")
        W.check(tile is not None, "the Sphere entry is in the Shapes flyout")
        if tile is not None:
            n0 = len(b.doc.history.changes)
            before = {m["id"] for m in meshes(b.doc, "sphere")}
            W.click(win, tile)
            at = QPoint(round(cx + CLICK[0] * rx), round(cy + CLICK[1] * ry))
            report["click"] = [at.x(), at.y(), CLICK]
            QTest.mouseMove(win, at)
            W.pump(0.4)
            QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
            W.pump(20, lambda: len(b.doc.history.changes) > n0 or v.status.startswith("Error"), "the sphere's change")
            W.pump(1.0)
            QTest.mouseMove(win, QPoint(8, 8))
            shot(win, "3-mirrored-eye", report)
            sp = [m for m in meshes(b.doc, "sphere") if m["id"] not in before]
            report["spheres"] = [{k: m.get(k) for k in ("id", "name", "mirror", "x", "y", "z")} for m in sp]
            W.check(len(sp) == 2, f"two spheres exist ({len(sp)})")
            mir = [m for m in sp if "(mirrored)" in str(m.get("name", ""))]
            W.check(len(mir) == 1, f"one is named '... (mirrored)' ({[m.get('name') for m in sp]})")
            orig = [m for m in sp if m not in mir]
            W.check(bool(mir) and bool(orig) and mir[0].get("mirror") == orig[0]["id"], "the copy's `mirror` is the other sphere")
            W.check(len(b.doc.history.changes) == n0 + 1, f"one undo step ({n0} -> {len(b.doc.history.changes)})")
            if len(sp) == 2:
                W.check(abs(sp[0].get("x", 0) + sp[1].get("x", 0)) < 1e-3 or abs(sp[0].get("x", 0) - sp[1].get("x", 0)) > 1e-3,
                        "the two spheres sit on opposite sides")

        # 4. touchpad turn, then Make this the shot
        QTest.keyClick(win, Qt.Key_V)
        W.pump(0.3)
        QTest.keyClick(win, Qt.Key_Escape)
        W.pump(0.3)
        W.check(v.mode == "shot", f"before the touchpad the view is on the shot ({v.mode})")
        pos = QPointF(top.x() + 0.5 * w, top.y() + 0.5 * h)
        gpos = QPointF(win.mapToGlobal(pos.toPoint()))
        QTest.mouseMove(win, pos.toPoint())
        W.pump(0.2)
        for i in range(8):
            ev = QWheelEvent(pos, gpos, QPoint(-14, 6), QPoint(-14, 6), Qt.NoButton, Qt.NoModifier, Qt.ScrollUpdate, False)
            QCoreApplication.sendEvent(win, ev)
            W.pump(0.03)
        W.pump(1.0)
        W.check(v.mode == "free", f"a two-finger scroll turned the view: Free camera ({v.mode})")
        t = texts(root)
        W.check(any("Free camera" in x for x in t), "the camera button says Free camera")
        shot(win, "4a-touchpad-turned", report)

        cams0, n0 = cameras(b.doc), len(b.doc.history.changes)
        btn = W.find(root, "takeShot")
        W.check(btn is not None, "the Make this the shot button is visible")
        if btn is not None:
            W.click(win, btn)
            W.pump(20, lambda: len(b.doc.history.changes) > n0 or v.status.startswith("Error"), "the take's change")
            W.pump(1.0)
            QTest.mouseMove(win, QPoint(8, 8))
            shot(win, "4b-shot-taken", report)
            cams1 = cameras(b.doc)
            W.check(cams1 != cams0, "the shot camera's values changed")
            W.check(len(b.doc.history.changes) == n0 + 1, f"one undo step ({n0} -> {len(b.doc.history.changes)})")
            W.check(v.mode == "shot", f"the view is back on the shot ({v.mode})")
            W.check(not v.status.startswith("Error"), f"no error ({v.status or '-'})")

        # 5. right-drag turns, a right click opens the menu
        QTest.mouseMove(win, QPoint(round(top.x() + 0.7 * w), round(top.y() + 0.3 * h)))
        W.pump(0.2)
        p0 = QPoint(round(top.x() + 0.7 * w), round(top.y() + 0.3 * h))
        n0 = len(b.doc.history.changes)
        QTest.mousePress(win, Qt.RightButton, Qt.NoModifier, p0)
        for i in range(1, 25):
            QTest.mouseMove(win, QPoint(p0.x() - 6 * i, p0.y() + 2 * i))
            W.pump(0.02)
        QTest.mouseRelease(win, Qt.RightButton, Qt.NoModifier, QPoint(p0.x() - 144, p0.y() + 48))
        W.pump(1.0)
        W.check(v.mode == "free", f"a right drag turned the view ({v.mode})")
        W.check("Duplicate" not in texts(root), "no menu after a right drag")
        W.check(len(b.doc.history.changes) == n0, "the view turn is not an undo step")
        QTest.mouseMove(win, QPoint(8, 8))
        shot(win, "5a-right-drag-turned", report)

        at = QPoint(round(top.x() + 0.3 * w), round(top.y() + 0.3 * h))
        QTest.mouseMove(win, at)
        W.pump(0.2)
        QTest.mouseClick(win, Qt.RightButton, Qt.NoModifier, at)
        shown = lambda: "Duplicate" in texts(root)  # noqa: E731  the menu's rows
        W.pump(5, shown, "the right-click menu")
        W.check(shown(), "a right click without moving opens the menu")
        W.pump(0.4)
        win.grabWindow().save(str(OUT / "5b-right-click-menu.png"))
        report["pictures"]["5b-right-click-menu"] = str(OUT / "5b-right-click-menu.png")
        QTest.keyClick(win, Qt.Key_Escape)
        W.pump(0.5)
        W.check(not shown(), "Esc closes the menu")
    except Exception as e:  # noqa: BLE001  a crash is a failed walk, said with its reason
        W.FAILS.append(f"the walk stopped: {type(e).__name__}: {e}")
        try:
            screen.win.grabWindow().save(str(OUT / "crash.png"))
        except Exception:  # noqa: BLE001
            pass
    finally:
        report["fails"] = W.FAILS
        (OUT / "cl6_walk.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
        screen.close()
        W.pump(1.0)
        shutil.rmtree(project, ignore_errors=True)
    print(f"{len(W.FAILS)} failed check(s); pictures in {OUT}")
    for f in W.FAILS:
        print("  " + f)
    app.quit()
    return 1 if W.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
