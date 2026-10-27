# Clay Spin walk (3d-v4): Spin tried by real input in the real window (behind the person's work, never focused).
# A scratch project with only a ground, two lights and the shot camera (clay_draw_walk's scene). Real input only:
#   1. Q (the key) turns Clay on; a picture "before";
#   2. the Spin tile in the Clay panel, found by its objectName (clayMakeSpin) and clicked; Spin is the chosen tool;
#   3. the pointer rests on the ground: Spin's axis (a vertical line) stands at it (picture "axis");
#   4. a real drag from the axis draws half a profile of a pot (up the right side, in and out), a picture while the
#      button is still held ("drawing"), the release; one new clay, selected, drawn (picture "after", and the changed
#      share of the pixels where the pot stands), one undo step;
#   5. Ctrl+Z: the clay is gone in one step (picture "undone"); Ctrl+Shift+Z: it is back (picture "redone").
# Pictures and numbers (clay_spin_walk.json) go to the out folder. The lead runs it:
#   heavy.ps1 run "sam: clay spin walk" gpu <venv python> apps\3d\tools\clay_spin_walk.py <out folder>
# Exit 0 = every check passed; else the failed checks are printed and it exits 1.
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-v4\spin-walk")
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_draw_walk as D  # noqa: E402  (its scene and helpers; puts this checkout's code first)
import clay_walk as W  # noqa: E402

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402

# half a pot's profile, from the axis out and up: (right of the axis, up from the start), in shares of the viewport's
# height: a foot, a round belly, a neck, a lip
PROFILE = [(0.0, 0.0), (0.06, 0.0), (0.11, 0.03), (0.14, 0.08), (0.14, 0.13), (0.11, 0.18), (0.07, 0.22), (0.06, 0.26),
           (0.08, 0.29), (0.0, 0.29)]


def shot(win, name):
    path = OUT / f"clay-spin-{name}.png"
    win.grabWindow().save(str(path))
    return str(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-clayspin-"))
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("scene.py", run_source(D.SCENE, "scene.py"))
    doc.save()
    screen = W.app3d.Screen(W.SIZE)
    report = {"pictures": {}}
    try:
        screen.show(doc, autosave=True)
        win, v = screen.win, screen.bridge.viewport
        W.pump(60, screen.ready, "the first picture")
        vp = W.find(win.contentItem(), "viewport3d")
        QTest.keyClick(win, Qt.Key_Q)
        W.pump(0.3)
        W.check(v.clay.on, "Q turns the Clay tool on")
        QTest.mouseMove(win, QPoint(8, 8))
        W.pump(30, lambda: D.settled(v), "the picture to settle")
        W.pump(0.3)
        before = win.grabWindow()
        report["pictures"]["before"] = shot(win, "1-before")

        tile = W.find(win.contentItem(), "clayMakeSpin")
        W.check(tile is not None, "the Spin tile is on the Clay panel (objectName clayMakeSpin)")
        if tile is None:
            raise RuntimeError("no Spin tile")
        W.click(win, tile)
        W.check(v.clay.tool == "spin", f"clicking Spin chooses it ({v.clay.tool})")

        top = vp.mapToScene(QPointF(0, 0))
        h = vp.height()
        start = QPoint(round(top.x() + 0.5 * vp.width()), round(top.y() + 0.78 * h))
        QTest.mouseMove(win, QPoint(start.x() - 6, start.y()))
        W.pump(0.2)
        QTest.mouseMove(win, start)
        W.pump(5, lambda: len(v.clay.drawObj.axis) > 0, "Spin's axis under the pointer")
        W.pump(0.4)
        W.check(len(v.clay.drawObj.axis) > 0, "resting the pointer on the ground shows Spin's axis")
        report["pictures"]["axis"] = shot(win, "2-axis")

        doc_, n0 = screen.bridge.doc, len(screen.bridge.doc.history.changes)
        clays0 = set(D.clays(doc_))
        pts = [QPoint(round(start.x() + dx * h), round(start.y() - dy * h)) for dx, dy in PROFILE]
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, pts[0])
        half = len(pts) // 2
        for i, p in enumerate(pts[1:], 1):
            for k in range(1, 7):                                       # six real moves between the corners
                a = pts[i - 1]
                QTest.mouseMove(win, QPoint(round(a.x() + (p.x() - a.x()) * k / 6), round(a.y() + (p.y() - a.y()) * k / 6)))
                W.pump(0.012)
            if i == half:
                W.pump(0.3)
                report["chipWhileDrawing"] = v.clay.drawObj.chip
                report["pictures"]["drawing"] = shot(win, "3-drawing")
        W.check(len(v.clay.drawObj.line) > 4, f"the profile shows while the button is held ({len(v.clay.drawObj.line)} points)")
        t0 = time.perf_counter()
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, pts[-1])
        W.pump(20, lambda: len(doc_.history.changes) > n0 or v.status.startswith("Error"), "the Spin's change")
        changed_ms = (time.perf_counter() - t0) * 1000
        W.pump(30, lambda: D.settled(v), "the picture")
        W.pump(0.1)
        shown_ms = (time.perf_counter() - t0) * 1000
        W.check(not v.status.startswith("Error"), f"no error ({v.status or '-'})")
        new = [c for c in D.clays(doc_) if c not in clays0]
        W.check(len(new) == 1, f"one new clay ({new})")
        W.check(len(doc_.history.changes) == n0 + 1, f"one undo step ({n0} -> {len(doc_.history.changes)})")
        W.check(bool(new) and screen.bridge.selected == new[0], f"the new clay is selected ({screen.bridge.selected})")
        QTest.mouseMove(win, QPoint(8, 8))
        W.pump(30, lambda: D.settled(v), "the picture without the pointer")
        W.pump(0.3)
        after = win.grabWindow()
        report["pictures"]["after"] = shot(win, "4-after")
        dpr = after.width() / win.width()
        box = (start.x() - 0.2 * h, start.y() - 0.32 * h, start.x() + 0.2 * h, start.y() + 0.03 * h)
        share = W.changed_share(before, after, box, dpr)
        W.check(share >= W.SEEN, f"the pot is in the picture ({share:.1%} of the pixels where it stands changed)")
        report["spin"] = {"changedMs": round(changed_ms), "shownMs": round(shown_ms), "newClays": new,
                          "points": len(pts), "pixelShare": round(share, 3)}

        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
        W.pump(1.0, lambda: not [c for c in D.clays(doc_) if c not in clays0])
        W.pump(30, lambda: D.settled(v), "the undone picture")
        W.pump(0.3)
        W.check(not [c for c in D.clays(doc_) if c not in clays0], "Ctrl+Z takes the pot back in one step")
        report["pictures"]["undone"] = shot(win, "5-undone")
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier)
        W.pump(2.0, lambda: bool([c for c in D.clays(doc_) if c not in clays0]))
        W.pump(30, lambda: D.settled(v), "the redone picture")
        W.pump(0.3)
        W.check(len([c for c in D.clays(doc_) if c not in clays0]) == 1, "Ctrl+Shift+Z puts it back")
        report["pictures"]["redone"] = shot(win, "6-redone")
    except Exception as e:  # noqa: BLE001  a crash is a failed walk, said with its reason
        W.FAILS.append(f"the walk stopped: {type(e).__name__}: {e}")
    finally:
        report["fails"] = W.FAILS
        (OUT / "clay_spin_walk.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        screen.close()
        W.pump(1.0)
        shutil.rmtree(project, ignore_errors=True)
    print(f"{len(W.FAILS)} failed check(s); numbers and pictures in {OUT}")
    for f in W.FAILS:
        print("  " + f)
    app.quit()
    return 1 if W.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
