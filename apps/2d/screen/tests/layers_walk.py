# Animation layers walk (2D): the kit's AnimLayers (⧉ beside Keys | Curves, layers2d.py) tried by real input in the
# real window, 1646 x 900, behind the person's work (never focused). A box moving on x (the Base); then, by real keys
# and mouse only (bridge calls only read state to check it):
#   1. ⧉, + New layer: a layer, chosen.
#   2. The box clicked on the canvas, 30 typed into its Rotation: a key ON THE LAYER (the Base's keys untouched), the
#      panel shows 30, the engine is sent the stack laid over the Base (scene: rotation 30 at the playhead).
#   3. The layer's weight slider dragged to about half: ONE undo step, weight ~0.5.
#   4. Its on switch clicked: off. 5. Ctrl+Z: on again.
# Pictures after each step go to the out folder. Not collected by pytest:
#   <venv python> apps\2d\screen\tests\layers_walk.py --out <folder>
# Exit 0 = every check passed; else the failed checks are printed and it exits 1.
import argparse
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import checkout_paths  # noqa: E402  (this checkout's code first, before any Rostrum import)
checkout_paths.use_this_checkout()

from PySide6.QtCore import QCoreApplication, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum2d import KIND, run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402

SIZE = (1646, 900)
SRC = '''
comp("c", width=1920, height=1080, fps=24, duration=4)
b = shape("box", w=300, h=300, x=700, y=540, fill="#4fa0ff")
b.key("x", {0: 700, 4: 1300}, ease="linear")
'''
FAILS: list[str] = []


def pump(seconds=0.0):
    end = time.perf_counter() + seconds
    while True:
        QCoreApplication.processEvents()
        if time.perf_counter() > end:
            return
        time.sleep(0.002)


def check(ok, line):
    print(("ok   " if ok else "FAIL ") + line)
    if not ok:
        FAILS.append(line)


def find(item, name):
    if item.objectName() == name and item.isVisible():
        return item
    for c in item.childItems():
        if (hit := find(c, name)) is not None:
            return hit
    return None


def click(win, item):
    p = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseMove(win, p)
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, p)
    pump(0.3)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--out", default=r"C:\Users\Sam\.rostrum\waves\results\3d-pr2-finish-pr3\2d")
    out = Path(a.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-2d-layerswalk-"))
    app = qt_app()  # noqa: F841
    from screen2d.session import Session
    from screen2d.stroke_steps import _scene_of
    from rostrum2d.scene import describe
    session = Session(SIZE, None)
    doc = Document.new(KIND, folder=str(project), item="proj")
    doc.run_script("a.py", run_source(SRC, "a.py"))
    session.files.put(doc)
    b, win = session.bridge, session.win
    doc = b.doc

    def snap(name):
        pump(0.6)
        win.grabWindow().save(str(out / f"layers-{name}.png"))

    def item(name):
        root = win.contentItem().parentItem() or win.contentItem()       # popovers live in the overlay beside it
        found = find(root, name)
        check(found is not None, f"'{name}' is on screen")
        return found

    def layers():
        return doc.data.get("animLayers") or []

    try:
        pump(3.0)
        # 1. ⧉ › + New layer
        click(win, item("animLayersButton"))
        pump(0.6)
        snap("0-popover")
        click(win, item("animLayerNew"))
        pump(0.6)
        check(len(layers()) == 1, f"+ New layer made one ({layers()})")
        lid = layers()[0]["id"] if layers() else ""
        check(b.animLayers.active == lid, f"the new layer is chosen ({b.animLayers.active!r})")
        snap("1-new-layer")
        QTest.keyClick(win, Qt.Key_Escape)
        pump(0.4)

        # 2. the box clicked on the canvas, Rotation typed: a key on the layer
        p = _scene_of(win, 700, 540)
        QTest.mouseMove(win, p)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, p)
        pump(0.6)
        check(b.multi.ids == ["box"], f"the box is picked ({b.multi.ids})")
        base = [dict(k) for k in doc.item("box")["keys"]]
        row = item("row:rotation")
        field = next((c for c in _walk(row) if c.objectName() == "grid:field"), None) if row else None
        check(field is not None, "Rotation's field is on screen")
        if field is not None:
            click(win, field)
            QTest.keyClick(win, Qt.Key_A, Qt.ControlModifier)
            for k in (Qt.Key_3, Qt.Key_0):
                QTest.keyClick(win, k)
            QTest.keyClick(win, Qt.Key_Return)
            pump(0.8)
        on_layer = [k for k in doc.item("box")["keys"] if k.get("layer") == lid]
        check(len(on_layer) == 1 and on_layer[0]["prop"] == "rotation", f"Rotation typed: one key on the layer ({on_layer})")
        check([k for k in doc.item("box")["keys"] if not k.get("layer")] == base, "the Base's keys untouched")
        shown = b.shown_values(doc.item("box")).get("rotation")
        check(shown is not None and abs(shown - 30) < 1e-6, f"the panel shows 30 ({shown})")
        node = next(n for n in describe(doc.data, None, None, None, None, [])["comp"]["layers"] if n["id"] == "box")
        sent = node.get("anim", {}).get("rotation", [])
        check(bool(sent) and abs(sent[0]["v"] - 30) < 1e-6, f"the engine is sent the layered rotation ({sent[:1]})")
        snap("2-key-on-layer")

        # 3. weight slider to about half: one undo step
        click(win, item("animLayersButton"))
        pump(0.5)
        sl = item("animLayerWeight_" + lid)
        n0 = len(doc.history.changes)
        if sl is not None:
            y = sl.height() / 2
            a0 = sl.mapToScene(QPointF(sl.width() * 0.97, y)).toPoint()
            a1 = sl.mapToScene(QPointF(sl.width() * 0.5, y)).toPoint()
            QTest.mouseMove(win, a0)
            QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, a0)
            for i in range(1, 9):
                QTest.mouseMove(win, QPoint(a0.x() + (a1.x() - a0.x()) * i // 8, a0.y()))
                pump(0.03)
            QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, a1)
            pump(0.5)
        w = layers()[0].get("weight", 1.0) if layers() else None
        check(w is not None and 0.35 < w < 0.65, f"the weight is about half ({w})")
        check(len(doc.history.changes) == n0 + 1, f"the weight drag: one undo step ({n0} -> {len(doc.history.changes)})")
        shown = b.shown_values(doc.item("box")).get("rotation")
        check(w is not None and shown is not None and abs(shown - 30 * w) < 1e-3, f"the panel shows 30 x weight ({shown})")
        snap("3-weight-half")

        # 4. off, 5. Ctrl+Z
        click(win, item("animLayerOn_" + lid))
        pump(0.5)
        check(bool(layers()) and layers()[0].get("on") is False, f"the switch: off ({layers()})")
        shown = b.shown_values(doc.item("box")).get("rotation")
        check(shown == 0, f"off: the Base's rotation shows ({shown})")
        snap("4-off")
        QTest.keyClick(win, Qt.Key_Escape)
        pump(0.3)
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
        pump(0.6)
        check(bool(layers()) and layers()[0].get("on", True) is True, f"Ctrl+Z: on again ({layers()})")
        snap("5-undone")
    finally:
        session.close()
        pump(0.5)
        shutil.rmtree(project, ignore_errors=True)
    if FAILS:
        print("FAILED:\n  " + "\n  ".join(FAILS))
        sys.exit(1)
    print("2D layers walk: every check passed")


def _walk(item):
    yield item
    for c in item.childItems():
        yield from _walk(c)


if __name__ == "__main__":
    main()
