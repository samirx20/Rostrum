# PR5 walk: a filled layer masked to a box's edges, by real input in the real 3D window (behind the person's work,
# never focused). Bridge calls only read state. A scratch project (ground, light, shot camera, a grey box); then:
#   1. a click on the box selects it; B: Paint (the box is laid flat, its shape kept for the masks); + (a layer) ... "1-layer"
#   2. Fill switched on (its toggle clicked): the layer covers the box; Fill colour shows; no Spread yet ......... "2-filled"
#   3. Mask › Edges (the list's entry clicked): "Finding edges…", then only the edges are painted; Spread and
#      Invert show ........................................................................................... "3-edges"
#   4. Ctrl+Z: no mask again (one step); Ctrl+Shift+Z: back; Final ........................................ "4-final"
# Pictures to the out folder (1646 x 900). The lead runs it: heavy.ps1 run "hem: masks walk" gpu <venv python>
#   apps\3d\tools\masks_walk.py <out folder>.  Exit 0 = every check passed.
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-pr5\masks")
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_walk as W  # noqa: E402  (puts this checkout's code first; its real-input helpers)

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402

W.OUT = OUT
SCENE = '''
grey = material("grey", baseColor="#5a5d63", roughness=0.5)
mesh("ground", shape="plane", width=3, depth=3)
mesh("box", shape="box", width=0.2, height=0.2, depth=0.2, ry=30, material=grey)
light("key", kind="rect", width=0.6, height=0.4, intensity=30, x=-0.5, y=0.7, z=0.6).aim((0, 0.1, 0))
cam = camera("cam", focalLength=50, y=0.3, z=0.8).aim((0, 0.1, 0))
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


def widget(row, kind):
    """The first visible item under `row` whose class name has `kind` (Toggle, ChoiceField)."""
    stack = [row] if row is not None else []
    while stack:
        it = stack.pop(0)
        if kind in it.metaObject().className() and it.isVisible():
            return it
        stack += it.childItems()
    return None


def snap(screen, name):
    QTest.mouseMove(screen.win, QPoint(8, 8))
    W.settled_picture(screen, screen.win).save(str(OUT / f"{name}.png"))
    print("picture", OUT / f"{name}.png")


def shown(root, name):
    r = W.find(root, f"row:{name}")
    return r is not None and r.isVisible()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-maskswalk-"))
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("scene.py", run_source(SCENE, "scene.py"))
    doc.save()
    screen = W.app3d.Screen(W.SIZE)
    try:
        screen.show(doc, autosave=True)
        win, v, b = screen.win, screen.bridge.viewport, screen.bridge
        root = win.contentItem()
        W.pump(90, screen.ready, "the first picture")
        vp = W.find(root, "viewport3d")
        W.pump(30, lambda: v._r.idle() and not v._next.isActive(), "the first settled picture")
        at = vp.mapToScene(vp.width() * 0.5, vp.height() * 0.55).toPoint()

        # 1. select, B, +
        QTest.mouseMove(win, at)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
        W.pump(10, lambda: b.selected == "box", "the box selected")
        W.check(b.selected == "box", f"a click on the box selects it ({b.selected})")
        QTest.keyClick(win, Qt.Key_B)
        W.pump(20, lambda: v.paint.on and bool(b.doc.item("box").get("uvs")), "Paint on, the box laid flat")
        W.click(win, W.find(root, "paintAddLayer"))
        W.pump(0.6)
        layer = (b.doc.item("box").get("paints") or [{}])[-1].get("id", "")
        W.check(bool(layer), "+ made a layer")
        W.check(shown(root, "fill") and shown(root, "shapeMask"), "the layer's Fill and Mask rows show")
        W.check(not shown(root, "maskSpread") and not shown(root, "fillColor"), "no Spread or Fill colour yet")
        snap(screen, "1-layer")

        # 2. Fill
        t = widget(W.find(root, "row:fill"), "Toggle")
        W.check(t is not None, "Fill's toggle is on screen")
        if t is not None:
            W.click(win, t)
        W.pump(1)
        W.check(b.doc.item(layer).get("fill") is True, "Fill clicked: the layer is filled")
        W.check(shown(root, "fillColor"), "Fill colour shows once filled")
        snap(screen, "2-filled")

        # 3. Mask › Edges
        f = widget(W.find(root, "row:shapeMask"), "ChoiceField")
        W.check(f is not None, "Mask's picker is on screen")
        if f is not None:
            W.click(win, f)
        W.pump(0.4)
        lst = W.find(root, "choiceList")
        opt = find_text(lst, "Edges") if lst is not None else None
        W.check(opt is not None, "the Mask list has Edges")
        if opt is not None:
            W.click(win, opt)
        W.pump(120, lambda: not v.paint.layerRows.busy, "the edges found")
        W.pump(1)
        W.check(b.doc.item(layer).get("shapeMask") == "edges", f"Mask is Edges ({b.doc.item(layer).get('shapeMask')})")
        W.check(shown(root, "maskSpread") and shown(root, "maskInvert"), "Spread and Invert show with a mask")
        snap(screen, "3-edges")

        # 4. undo, redo, Final
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
        W.pump(1)
        W.check(b.doc.item(layer).get("shapeMask", "none") == "none", "Ctrl+Z: no mask (one step)")
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier)
        W.pump(1)
        W.check(b.doc.item(layer).get("shapeMask") == "edges", "Ctrl+Shift+Z: Edges again")
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
