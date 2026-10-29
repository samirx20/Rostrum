# PR4 walk: Stamp (an "alpha") by real input in the real 3D window (behind the person's work, never focused). Bridge
# calls only read state, except the picture file handed to Load picture… the way its file dialog would (as 2D's
# `choicefile` step does). A scratch project (ground, light, shot camera, one clay); then:
#   1. a click on the clay selects it; B: Paint; + (a layer); Paints › Relief (the list's entry clicked) .... "1-relief-layer"
#   2. Stamp clicked (Brush | Stamp shows only on a Relief layer): the rows are Picture, Size, Depth, Turn ... "2-stamp-rows"
#   3. Picture › Load picture… (a white ring on black, made here): it is the stamp's picture
#   4. one click on the clay: exactly one stroke landed on the Relief layer, one undo step ................. "3-stamped"
#   5. Ctrl+Z: the stroke is gone; Ctrl+Shift+Z: back; Shift+F (Final): the ring pressed in ................ "4-final"
# Pictures to the out folder (1646 x 900). The lead runs it: heavy.ps1 run "hem: stamp walk" gpu <venv python>
#   apps\3d\tools\stamp_walk.py <out folder>.  Exit 0 = every check passed.
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-pr4-finish\alphas")
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_walk as W  # noqa: E402  (puts this checkout's code first; its real-input helpers)

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from PySide6.QtCore import Q_ARG, QMetaObject, QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document, Who  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402

W.OUT = OUT
SCENE = '''
clayc = material("clayc", baseColor="#8a7f78", roughness=0.5)
mesh("ground", shape="plane", width=3, depth=3)
light("key", kind="rect", width=0.6, height=0.4, intensity=30, x=-0.5, y=0.7, z=0.6).aim((0, 0.1, 0))
cam = camera("cam", focalLength=50, y=0.14, z=0.78).aim((0, 0.1, 0))
shot("s", camera=cam, fps=24, start=0, end=2)
'''


def find_text(root, text):
    for c in root.childItems():
        if c.isVisible() and c.property("text") == text:
            return c
        hit = find_text(c, text) if c.isVisible() else None
        if hit is not None:
            return hit
    return None


def snap(screen, name):
    QTest.mouseMove(screen.win, QPoint(8, 8))
    W.settled_picture(screen, screen.win).save(str(OUT / f"{name}.png"))
    print("picture", OUT / f"{name}.png")


def ring(path: Path):
    yy, xx = np.mgrid[:256, :256]
    d = np.hypot(xx - 128, yy - 128)
    Image.fromarray(((d > 70) & (d < 110)).astype(np.uint8) * 255).save(path)


def relief_strokes(doc):
    return [s for p in doc.item("blob").get("paints", []) if p.get("channel") == "height" for s in p["strokes"]]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-stampwalk-"))
    ring(project / "ring.png")
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("scene.py", run_source(SCENE, "scene.py"))
    doc.apply([{"op": "clay.add", "args": {"id": "blob", "at": [0, 0.1, 0], "radius": 0.1, "material": "clayc"}}],
              Who.person())
    doc.save()
    screen = W.app3d.Screen(W.SIZE)
    try:
        screen.show(doc, autosave=True)
        win, v, b = screen.win, screen.bridge.viewport, screen.bridge
        root = win.contentItem()
        W.pump(90, screen.ready, "the first picture")
        vp = W.find(root, "viewport3d")
        W.pump(30, lambda: v._r.idle() and not v._next.isActive(), "the first settled picture")
        mid, _ = W.clay_on_screen(screen, "blob", vp)
        at = QPoint(round(mid.x()), round(mid.y()))

        # 1. select, B, +, Paints › Relief
        QTest.mouseMove(win, at)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
        W.pump(10, lambda: b.selected == "blob", "the clay selected")
        QTest.keyClick(win, Qt.Key_B)
        W.pump(3, lambda: v.paint.on, "Paint on")
        W.check(W.find(root, "paintHow") is None or not W.find(root, "paintHow").isVisible(),
                "no Brush | Stamp before a Relief layer")
        W.click(win, W.find(root, "paintAddLayer"))
        W.pump(0.6)
        W.click(win, W.find(root, "paintChannel"))
        W.pump(0.4)
        lst = W.find(root, "choiceList")
        opt = find_text(lst, "Relief") if lst is not None else None
        W.check(opt is not None, "the Paints list has Relief")
        if opt is not None:
            W.click(win, opt)
        W.pump(0.6)
        W.check(v.paint.activeChannel == "height", f"the layer paints Relief ({v.paint.activeChannel})")
        snap(screen, "1-relief-layer")

        # 2. Stamp
        how = W.find(root, "paintHow")
        W.check(how is not None and how.isVisible(), "Brush | Stamp shows on a Relief layer")
        stamp = find_text(how, "Stamp") if how is not None else None
        if stamp is not None:
            W.click(win, stamp)
        W.pump(0.6)
        W.check(v.paint.how == "stamp", "Stamp clicked")
        for name in ("texture", "size", "depth", "turn"):
            row = W.find(root, f"row:{name}")
            W.check(row is not None and row.isVisible(), f"the stamp's {name} row is on screen")
        W.check(W.find(root, "row:color") is None, "the brush's Colour row is gone while stamping")
        snap(screen, "2-stamp-rows")

        # 3. Load picture… (the file handed in as the dialog would)
        row = W.find(root, "row:texture")
        if row is not None:
            QMetaObject.invokeMethod(row, "loadChoice", Q_ARG("QVariant", str(project / "ring.png")))
        W.pump(0.4)
        W.check(v.paint.brush.stamp["texture"].startswith("brushtip_"), "the loaded picture is the stamp's picture")

        # 4. one click on the clay
        n = len(relief_strokes(b.doc))
        QTest.mouseMove(win, at)
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, at)
        W.pump(0.1)
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, at)
        W.pump(20, lambda: len(relief_strokes(b.doc)) > n, "the stamp's stroke")
        got = relief_strokes(b.doc)
        W.check(len(got) == n + 1, f"one click laid exactly one stamp ({len(got) - n})")
        W.check(bool(got) and len(got[-1].get("anchors") or []) == 1, "the stamp is one dab on the clay's surface")
        snap(screen, "3-stamped")

        # 5. undo, redo, Final
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
        W.pump(1)
        W.check(len(relief_strokes(b.doc)) == n, "Ctrl+Z takes the stamp back (one step)")
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier)
        W.pump(1)
        W.check(len(relief_strokes(b.doc)) == n + 1, "Ctrl+Shift+Z puts it back")
        QTest.keyClick(win, Qt.Key_B)
        W.pump(1)
        QTest.keyClick(win, Qt.Key_F, Qt.ShiftModifier)
        W.pump(25)
        snap(screen, "4-final")
        W.check(not v.status.startswith("Error"), f"no viewport error ({v.status or '-'})")
    finally:
        screen.close()
        app.processEvents()
        shutil.rmtree(project, ignore_errors=True)
    if W.FAILS:
        print(f"\n{len(W.FAILS)} check(s) failed: " + " | ".join(W.FAILS))
        sys.exit(1)
    print("\nevery check passed")


if __name__ == "__main__":
    main()
