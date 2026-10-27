# CL3b pictures (3d-v4): the three states the lead asked to see, in a background window at 1646 x 900, by real input.
# A scratch project with a ground, two lights and the shot camera; Q turns Clay on (Draw), one real pear outline makes a
# body. Then:
#   (a) the Clay panel with the Steps list: is it in view without scrolling? "cl3b-a1-more-closed" (the "More" fold
#       closed, as it opens), then the fold clicked open: "cl3b-a2-more-open". The fold is found by objectName; the first
#       of MORE_NAMES that is on screen is used, and none = a failed check naming what is expected (clayMore);
#   (b) V (the select tool), the pointer resting on the body: "cl3b-b1-hover" (a thin outline), then a click:
#       "cl3b-b2-selected". Pictures only plus the selection check; the outline's thinness is for the eye;
#   (c) back in Clay with Draw on (Q), a shape picked from the rail (Shapes -> Box, the same objectNames the draw walk
#       uses: rail_shapes, fly_mesh:box): "cl3b-c1-shape-picked" (pointer over the ground), then one press on the ground:
#       "cl3b-c2-shape-placed". Checks: the press places a box (and does not draw: no new clay, no new step on the body).
# Numbers and the checks (clay_cl3b_shots.json) and the pictures go to the out folder. The lead runs it:
#   heavy.ps1 run "sam: cl3b shots" gpu <venv python> apps\3d\tools\clay_cl3b_shots.py <out folder>
# Exit 0 = every check passed; else the failed checks are printed and it exits 1.
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-v4\cl3b-shots")
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

# the fold's objectName is not in the tree yet (another member is writing it); the expected one first
MORE_NAMES = ["the kit's More row in clayPanel (its text)"]


def find_text(root, text):
    """The first visible item under `root` showing `text` (the kit's More row has no objectName of its own)."""
    for c in root.childItems():
        if not c.isVisible():
            continue
        if c.property("text") == text:
            return c
        hit = find_text(c, text)
        if hit is not None:
            return hit
    return None


def shot(win, name, report):
    W.pump(30, lambda: D.settled(win_view(win)), "the picture to settle")
    W.pump(0.3)
    path = OUT / f"{name}.png"
    win.grabWindow().save(str(path))
    report["pictures"][name] = str(path)


_VIEW = []


def win_view(win):
    return _VIEW[0]


def scene_box(item):
    p = item.mapToScene(QPointF(0, 0))
    return p.x(), p.y(), item.width(), item.height()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-claycl3b-"))
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("scene.py", run_source(D.SCENE, "scene.py"))
    doc.save()
    screen = W.app3d.Screen(W.SIZE)
    report = {"pictures": {}, "notes": []}
    try:
        screen.show(doc, autosave=True)
        win, v = screen.win, screen.bridge.viewport
        _VIEW.append(v)
        b = screen.bridge
        W.pump(60, screen.ready, "the first picture")
        vp = W.find(win.contentItem(), "viewport3d")
        QTest.keyClick(win, Qt.Key_Q)
        W.pump(0.3)
        top = vp.mapToScene(QPointF(0, 0))
        w, h = vp.width(), vp.height()
        cx, cy, rx, ry = top.x() + 0.5 * w, top.y() + 0.6 * h, 0.12 * h, 0.25 * h
        body = D.draw(screen, win, "Body", D.pear(cx, cy, rx, ry), OUT, rest=0.1)
        clay = body["newClays"][0] if body["newClays"] else ""
        W.check(bool(clay), f"a body was drawn ({body['newClays']})")
        if not clay:
            raise RuntimeError("no body to test with")
        QTest.mouseMove(win, QPoint(8, 8))
        W.pump(0.3)

        # (a) the Steps list in the Clay panel
        panel = W.find(win.contentItem(), "clayPanel")
        steps = W.find(win.contentItem(), "claySteps")
        W.check(panel is not None and steps is not None, "the Clay panel and its Steps list are on screen")
        if panel is not None and steps is not None:
            px, py, pw, ph = scene_box(panel)
            sx, sy, sw, sh = scene_box(steps)
            inside = sy >= py and sy + sh <= py + ph and sy + sh <= win.height()
            report["steps"] = {"panel": [round(py), round(ph)], "steps": [round(sy), round(sh)]}
            W.check(inside, f"the Steps list is in view without scrolling (list y {sy:.0f}..{sy + sh:.0f}, panel {py:.0f}..{py + ph:.0f})")
        shot(win, "cl3b-a1-more-closed", report)
        more = find_text(panel, "More") if panel is not None else None       # the kit's More row (its head)
        W.check(more is not None, f"the More fold is on screen (expected objectName clayMore; tried {MORE_NAMES})")
        if more is not None and panel is not None:
            mx, my, mw, mh = scene_box(more)
            px, py, pw, ph = scene_box(panel)
            W.check(my + mh <= py + ph, f"the More row is in view without scrolling (y {my:.0f}..{my + mh:.0f}, panel ends {py + ph:.0f})")
        if more is not None:
            W.click(win, more)
            W.pump(0.5)
            QTest.mouseMove(win, QPoint(8, 8))
            shot(win, "cl3b-a2-more-open", report)
            W.click(win, more)                                          # and closed again for what follows
            W.pump(0.3)

        # (c) a shape picked from the rail while Clay's Draw is on: the next press places it
        W.check(v.clay.on and v.clay.tool == "draw", f"Clay is on with Draw before the rail pick ({v.clay.tool})")
        rail = W.find(win.contentItem(), "rail_shapes")
        W.check(rail is not None, "the Shapes rail button is there")
        W.click(win, rail)
        box_tile = W.find(win.contentItem(), "fly_mesh:box")
        W.check(box_tile is not None, "the Box entry is in the Shapes flyout")
        if rail is not None and box_tile is not None:
            clays_before, changes = set(D.clays(b.doc)), len(b.doc.history.changes)
            n_steps = D.steps_of(b.doc, clay)
            W.click(win, box_tile)
            at = QPoint(round(top.x() + 0.22 * w), round(top.y() + 0.8 * h))
            QTest.mouseMove(win, at)
            W.pump(0.5)
            report["clayAfterRailPick"] = {"on": bool(v.clay.on), "tool": v.clay.tool}
            shot(win, "cl3b-c1-shape-picked", report)
            QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
            W.pump(20, lambda: len(b.doc.history.changes) > changes or v.status.startswith("Error"), "the press's change")
            W.pump(1.0)
            shot(win, "cl3b-c2-shape-placed", report)
            sel = b.selected
            W.check(bool(sel) and b.doc.has(sel) and b.doc.item(sel).get("shape") == "box",
                    f"the press placed a box ({sel}: {b.doc.item(sel).get('shape') if sel and b.doc.has(sel) else None})")
            W.check(set(D.clays(b.doc)) == clays_before and D.steps_of(b.doc, clay) == n_steps,
                    "the press drew nothing: no new clay, no new step on the body")
            W.check(len(b.doc.history.changes) == changes + 1, f"one undo step ({changes} -> {len(b.doc.history.changes)})")

        # (b) Draw on (Q), the pointer resting on the body (not selected: the box is): the thin hover outline a drag
        # from there joins; then the select tool (V) and a click: the selection's outline
        QTest.keyClick(win, Qt.Key_Q)
        W.pump(0.5)
        W.check(v.clay.on, "Q: Clay on again (Draw) for the hover")
        W.check(b.selected != clay, f"the body is not selected before the hover ({b.selected})")
        rest = QPoint(round(cx), round(cy))
        QTest.mouseMove(win, QPoint(rest.x() + 20, rest.y()))
        W.pump(0.2)
        QTest.mouseMove(win, rest)
        W.pump(0.6)
        shot(win, "cl3b-b1-hover", report)
        QTest.keyClick(win, Qt.Key_V)
        W.pump(0.3)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, rest)
        W.pump(20, lambda: b.selected == clay, "the body selected by the click")
        W.pump(0.5)
        QTest.mouseMove(win, QPoint(8, 8))
        shot(win, "cl3b-b2-selected", report)
        W.check(b.selected == clay, f"a click on the body selects it ({b.selected})")
    except Exception as e:  # noqa: BLE001  a crash is a failed run, said with its reason
        W.FAILS.append(f"the run stopped: {type(e).__name__}: {e}")
    finally:
        report["fails"] = W.FAILS
        (OUT / "clay_cl3b_shots.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
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
