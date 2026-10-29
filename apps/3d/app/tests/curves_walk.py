# Curves walk (3d-people PR2): the timeline's Curves (the kit's CurveEditor.qml on curves3d.py) tried by real input in
# the real window, 1646 x 900, behind the person's work (never focused). The sample scene with keys on two items; then,
# by real keys and mouse only (bridge calls only read state to check it):
#   1. Alt+2 (Animate page), a click on Keys | Curves' "Curves": nothing picked, so every animated item's curves show.
#   2. A right-click on a key on the curve: that key is picked (its item's curves alone show), the Ease list opens; Esc.
#   3. "All curves" in the view: both items' curves again, grouped by item.
#   4. A key dragged right and up: ONE undo step, time and value changed.
#   5. A key clicked (picked: its handles show), its out-handle dragged: ONE undo step, the ease is custom.
#   6. Ctrl+Z: the ease is back.
# Pictures after each step go to the out folder. Not collected by pytest:
#   <venv python> apps\3d\app\tests\curves_walk.py --out <folder>
# Exit 0 = every check passed; else the failed checks are printed and it exits 1.
import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import clay_walk as W  # noqa: E402  (puts this checkout's code first; its real-input helpers)

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document, Who  # noqa: E402
from rostrum_core.keys import keys_of  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d.sample import SOURCE  # noqa: E402

import main as app3d  # noqa: E402

SIZE = (1646, 900)
KEYS = [("block", "y", 0.0, 0.15), ("block", "y", 1.5, 0.6), ("ball", "x", 0.5, 0.48), ("ball", "x", 1.75, -0.3)]


class Walk:
    def __init__(self, screen, out):
        self.s, self.out, self.win, self.b = screen, out, screen.win, screen.bridge

    def snap(self, name):
        W.pump(0.5)
        self.win.grabWindow().save(str(self.out / f"curves-{name}.png"))

    def item(self, name):
        found = W.find(self.win.contentItem(), name)
        W.check(found is not None, f"'{name}' is on screen")
        return found

    def part(self, name, fx, fy=0.5):
        """A window point at (fx, fy) of the named item's box."""
        it = self.item(name)
        p = it.mapToScene(QPointF(it.width() * fx, it.height() * fy))
        return QPoint(round(p.x()), round(p.y()))

    def at(self, field_id, t, v):
        """Where (t s, v) of a curve is drawn, as CurveEditor.qml places it (px / py), in window px."""
        plot = self.item("curvePlot")
        f = next(f for f in self.b.curves.fields if f["id"] == field_id)
        dur = self.b.frameInfo["duration"]
        x = 8 + t / dur * (plot.width() - 16)
        y = 14 + (f["hi"] - v) / (f["hi"] - f["lo"]) * (plot.height() - 28)
        p = plot.mapToScene(QPointF(x, y))
        return QPoint(round(p.x()), round(p.y()))

    def drag(self, a, b, steps=8):
        QTest.mouseMove(self.win, a)
        QTest.mousePress(self.win, Qt.LeftButton, Qt.NoModifier, a)
        for i in range(1, steps + 1):
            QTest.mouseMove(self.win, QPoint(a.x() + (b.x() - a.x()) * i // steps, a.y() + (b.y() - a.y()) * i // steps))
            W.pump(0.03)
        QTest.mouseRelease(self.win, Qt.LeftButton, Qt.NoModifier, b)
        W.pump(0.3)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--out", default=r"C:\Users\Sam\.rostrum\waves\results\3d-people-pr2\curves")
    out = Path(a.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-curveswalk-"))
    app = qt_app()  # noqa: F841
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("sample.py", run_source(SOURCE.replace("end=2)", "end=4)"), "sample.py"))
    doc.apply([{"op": "key.add", "target": [o], "args": {"prop": p, "t": t, "v": v}} for o, p, t, v in KEYS], Who.person())
    doc.save()
    screen = app3d.Screen(SIZE)
    try:
        screen.show(doc, autosave=True)
        w = Walk(screen, out)
        b, win, cv = w.b, w.win, w.b.curves
        W.pump(60, screen.ready, "the first picture")
        QTest.keyClick(win, Qt.Key_2, Qt.AltModifier)
        W.pump(1.0)
        W.check(b.page == "animate", f"Alt+2: the Animate page ({b.page})")

        # 1. Curves
        at = w.part("keysCurves", 0.75)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
        W.pump(0.8)
        W.check(cv.on, "Curves clicked: the curve view is on")
        W.check({"block", "ball", "cam"} == {f["group"] for f in cv.fields}, f"nothing picked: every animated item's curves ({[f['id'] for f in cv.fields]})")
        w.snap("1-all-nothing-picked")

        # 2. right-click a key: picked, the Ease list
        k_block = keys_of(doc.item("block"), "y")
        p = w.at("block.y", k_block[1]["t"], k_block[1]["v"])
        QTest.mouseMove(win, p)
        QTest.mouseClick(win, Qt.RightButton, Qt.NoModifier, p)
        W.pump(0.8)
        W.check(list(b.keys.ids) == [k_block[1]["id"]], f"right-click picked the key ({list(b.keys.ids)})")
        W.check([f["id"] for f in cv.fields] == ["block.y"], f"its item's curves alone ({[f['id'] for f in cv.fields]})")
        w.snap("2-key-menu")
        QTest.keyClick(win, Qt.Key_Escape)
        W.pump(0.4)

        # 3. All curves
        W.check(cv.canAll, "All curves is offered (another item is animated)")
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, w.part("curvesWhich", 0.75))
        W.pump(0.6)
        W.check({f["group"] for f in cv.fields} == {"block", "ball", "cam"}, f"All curves: every animated item (the sample camera moves too) ({[f['id'] for f in cv.fields]})")
        w.snap("3-all-curves")

        # 4. drag a key
        n0 = len(doc.history.changes)
        k = keys_of(doc.item("ball"), "x")[1]
        p0 = w.at("ball.x", k["t"], k["v"])
        w.drag(p0, QPoint(p0.x() - 60, p0.y() - 40))
        k2 = doc.item(k["id"])
        W.check(len(doc.history.changes) == n0 + 1, f"the key drag: one undo step ({n0} -> {len(doc.history.changes)})")
        W.check(k2["t"] < k["t"] and k2["v"] > k["v"], f"the key moved earlier and up ({k['t']}, {k['v']} -> {k2['t']}, {k2['v']})")
        w.snap("4-key-dragged")

        # 5. pick a key, drag its out-handle
        k0 = keys_of(doc.item("block"), "y")[0]
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, w.at("block.y", k0["t"], k0["v"]))
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, w.at("block.y", k0["t"], k0["v"]))
        W.pump(0.6)
        f = next(f for f in cv.fields if f["id"] == "block.y")
        W.check(len(f["stretches"]) == 1, f"the picked key's handles show ({f['stretches']})")
        w.snap("5a-handles")
        n1 = len(doc.history.changes)
        h1 = f["stretches"][0]["h1"]
        p1 = w.at("block.y", h1[0], h1[1])
        w.drag(p1, QPoint(p1.x() + 40, p1.y() - 50))
        W.check(len(doc.history.changes) == n1 + 1, f"the handle drag: one undo step ({n1} -> {len(doc.history.changes)})")
        W.check(doc.item(k0["id"])["ease"] == "custom", f"the ease is custom ({doc.item(k0['id']).get('ease')})")
        w.snap("5b-handle-dragged")

        # 6. Ctrl+Z
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
        W.pump(0.6)
        W.check(doc.item(k0["id"])["ease"] == "smooth", f"Ctrl+Z: the ease is back ({doc.item(k0['id']).get('ease')})")
        w.snap("6-undone")
    finally:
        screen.close()
        W.pump(0.5)
        shutil.rmtree(project, ignore_errors=True)
    if W.FAILS:
        print("FAILED:\n  " + "\n  ".join(W.FAILS))
        sys.exit(1)
    print("curves walk: every check passed")


if __name__ == "__main__":
    main()
