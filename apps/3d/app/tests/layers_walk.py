# Animation layers walk (3d-people PR2): the kit's AnimLayers (⧉ in the timeline header, layers3d.py) tried by real input
# in the real window, 1646 x 900, behind the person's work (never focused). The sample scene with the ball moving on x
# (the Base); then, by real keys and mouse only (bridge calls only read state to check it):
#   1. Alt+2 (Animate page), ⧉, + New layer: a layer, chosen.
#   2. The ball picked, 0.5 typed into its Z: a key ON THE LAYER (the Base's keys untouched); the value shown is 0.5.
#   3. The layer's weight slider dragged down past half and back to half in one drag: the slider lives through the whole
#      drag (its row updates in place), ONE undo step, weight ~0.5.
#   4. Its on switch clicked: off. 5. Ctrl+Z: on again.
# Pictures after each step go to the out folder. Not collected by pytest:
#   <venv python> apps\3d\app\tests\layers_walk.py --out <folder>
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
import shiboken6  # noqa: E402
from rostrum_core import Document, Who  # noqa: E402
from rostrum_core.keys import keys_of  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d.sample import SOURCE  # noqa: E402

import main as app3d  # noqa: E402

SIZE = (1646, 900)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--out", default=r"C:\Users\Sam\.rostrum\waves\results\3d-people-pr2\layers\walk")
    out = Path(a.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-layerswalk-"))
    app = qt_app()  # noqa: F841
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("sample.py", run_source(SOURCE.replace("end=2)", "end=4)"), "sample.py"))
    doc.apply([{"op": "key.add", "target": ["ball"], "args": {"prop": "x", "t": t, "v": v}} for t, v in ((0, 0.48), (1.5, -0.3))],
              Who.person())
    doc.save()
    screen = app3d.Screen(SIZE)
    win = None

    def snap(name):
        W.pump(0.5)
        win.grabWindow().save(str(out / f"layers-{name}.png"))

    def item(name):
        root = win.contentItem().parentItem() or win.contentItem()      # popovers live in the overlay beside it
        found = W.find(root, name)
        W.check(found is not None, f"'{name}' is on screen")
        return found

    def layers():
        return doc.data.get("animLayers") or []

    try:
        screen.show(doc, autosave=True)
        b, win = screen.bridge, screen.win
        W.pump(60, screen.ready, "the first picture")
        QTest.keyClick(win, Qt.Key_2, Qt.AltModifier)
        W.pump(1.0)
        W.check(b.page == "animate", f"Alt+2: the Animate page ({b.page})")

        # 1. ⧉ › + New layer
        W.click(win, item("animLayersButton"))
        W.pump(0.8)
        snap("0-popover")
        W.click(win, item("animLayerNew"))
        W.pump(0.6)
        W.check(len(layers()) == 1, f"+ New layer made one ({layers()})")
        lid = layers()[0]["id"] if layers() else ""
        snap("1-new-layer")
        QTest.keyClick(win, Qt.Key_Escape)
        W.pump(0.4)

        # 2. the ball picked, Z typed: a key on the layer
        base_keys = [dict(k) for k in doc.item("ball")["keys"]]
        b_row = next((it for it in _texts(win.contentItem(), "ball")), None)
        W.check(b_row is not None, "the ball's row is on screen")
        if b_row is not None:
            W.click(win, b_row)
        W.pump(0.4)
        W.check(b.selected == "ball", f"the ball is picked ({b.selected})")
        row = item("row:z")
        field = next((c for c in _walk(row) if c.objectName() == "grid:field"), row) if row else None
        if field is not None:
            W.click(win, field)
            QTest.keyClick(win, Qt.Key_A, Qt.ControlModifier)
            for k in (Qt.Key_0, Qt.Key_Period, Qt.Key_5):
                QTest.keyClick(win, k)
            QTest.keyClick(win, Qt.Key_Return)
            W.pump(0.8)
        on_layer = [k for k in doc.item("ball")["keys"] if k.get("layer") == lid]
        W.check(len(on_layer) == 1 and on_layer[0]["prop"] == "z", f"Z typed: one key on the layer ({on_layer})")
        W.check([k for k in doc.item("ball")["keys"] if not k.get("layer")] == base_keys, "the Base's keys untouched")
        W.check(keys_of(doc.item("ball"), "z") == [], "the Base has no z keys (keys_of reads the Base)")
        snap("2-key-on-layer")

        # 3. weight slider to about half: one undo step
        W.click(win, item("animLayersButton"))
        W.pump(0.5)
        sl = item("animLayerWeight_" + lid)
        n0 = len(doc.history.changes)
        if sl is not None:
            y = sl.height() / 2
            a0, a1, a2 = (sl.mapToScene(QPointF(sl.width() * f, y)).toPoint() for f in (0.97, 0.2, 0.5))
            QTest.mouseMove(win, a0)
            QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, a0)
            for frm, to in ((a0, a1), (a1, a2)):           # down past half, then back: the drag must live through its own changes
                for i in range(1, 9):
                    QTest.mouseMove(win, QPoint(frm.x() + (to.x() - frm.x()) * i // 8, frm.y()))
                    W.pump(0.03)
                if to is a1:
                    mid = layers()[0].get("weight", 1.0) if layers() else None
                    W.check(mid is not None and mid < 0.35, f"mid-drag: the weight follows the pointer ({mid})")
            W.check(shiboken6.isValid(sl), "the weight slider is the same one all through the drag (its row updated in place)")
            QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, a2)
            W.pump(0.5)
        w = layers()[0].get("weight", 1.0) if layers() else None
        W.check(w is not None and 0.35 < w < 0.65, f"the weight is about half ({w})")
        W.check(len(doc.history.changes) == n0 + 1, f"the weight drag: one undo step ({n0} -> {len(doc.history.changes)})")
        snap("3-weight-half")

        # 4. off, 5. Ctrl+Z
        W.click(win, item("animLayerOn_" + lid))
        W.pump(0.5)
        W.check(layers() and layers()[0].get("on") is False, f"the switch: off ({layers()})")
        snap("4-off")
        QTest.keyClick(win, Qt.Key_Escape)
        W.pump(0.3)
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
        W.pump(0.6)
        W.check(layers() and layers()[0].get("on", True) is True, f"Ctrl+Z: on again ({layers()})")
        snap("5-undone")
    finally:
        screen.close()
        W.pump(0.5)
        shutil.rmtree(project, ignore_errors=True)
    if W.FAILS:
        print("FAILED:\n  " + "\n  ".join(W.FAILS))
        sys.exit(1)
    print("layers walk: every check passed")


def _walk(item):
    yield item
    for c in item.childItems():
        yield from _walk(c)


def _texts(root, text):
    """Visible items whose text is `text` (a scene list row's name)."""
    for it in _walk(root):
        if it.property("text") == text and it.isVisible() and it.width() > 0:
            yield it


if __name__ == "__main__":
    main()
