# PR5 walk: a block's setting shown on the material, by real input in the real window (behind the person's work,
# never focused). The scene is made before the window opens (the start scene, a sphere with a material whose blocks
# hold a Noise); then, by real mouse and keys only (the document is only read):
#   1. a click on the sphere selects it; Edit as blocks; a click on Noise's title picks it; Show on material ▾ ›
#      Scale: the block's `shown` holds scale, one undo step ...................................... "1-show-menu"
#   2. Esc: the item's own settings; the row "Noise · Scale" is with the material's; 12 typed in it: the Noise's
#      Scale is 12 (graph.set), one undo step ................................................... "2-shown-row"
#   3. Ctrl+Z: Scale back; Ctrl+Z: the row is gone ............................................ "3-undone"
# Run: heavy.ps1 run "hem: shown walk" gpu <venv python> apps\3d\tools\shown_setting_walk.py <out folder>. Exit 0 = all passed.
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-pr4-finish\shown")
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_walk as W  # noqa: E402
import blocks23_walk as B  # noqa: E402

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Who  # noqa: E402
from rostrum3d import graph as G  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d import files_3d  # noqa: E402

chk = B.chk


def snap(screen, name):
    W.settled_picture(screen, screen.win).save(str(OUT / f"{name}.png"))
    print("picture", OUT / f"{name}.png")


def noise_of(doc):
    return next(b for b in G.graph_of(doc.item("mat"))["blocks"] if b["type"] == "noise")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-shownwalk-"))
    app = qt_app()  # noqa: F841
    doc = files_3d.blank(project)
    sam = Who.person()
    doc.apply([{"op": "material.add", "args": {"id": "mat", "name": "Speckle"}},
               {"op": "mesh.add", "args": {"id": "ball", "shape": "sphere", "radius": 0.3, "y": 0.3, "material": "mat"}},
               {"op": "graph.add", "target": ["mat"], "args": {"type": "noise", "id": "noise_1"}},   # no place: graph.add puts it left of Surface
               {"op": "graph.connect", "target": ["mat"], "args": {"from": "noise_1.value", "to": "surface.roughness"}}],
              sam)
    doc.save()
    screen = W.app3d.Screen(W.SIZE)
    try:
        screen.show(doc, autosave=True)
        win, v, b = screen.win, screen.bridge.viewport, screen.bridge
        D = b.doc
        W.pump(90, screen.ready, "the first picture")
        vp = W.find(win.contentItem(), "viewport3d")
        W.pump(30, lambda: v._r.idle(), "the first settled picture")

        # 1. select, Edit as blocks, pick Noise, Show on material › Scale
        at = vp.mapToScene(QPointF(vp.width() * 0.5, vp.height() * 0.55)).toPoint()
        QTest.mouseMove(win, at)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
        W.pump(30, lambda: b.selected == "ball", "the sphere selected")   # the first pick waits for the engine
        chk(b.selected == "ball", f"a click on the sphere selects it ({b.selected})")
        link = B.reveal(win, "editAsBlocks", "the material's Edit as blocks row")
        if link is not None:
            B.click(win, link)
        W.pump(10, lambda: b.blocks.open, "the block view")
        W.pump(0.5)
        QTest.keyClick(win, Qt.Key_F)                   # F fits every block in the view
        W.pump(0.8)
        head = B.control(win, "blockHeader:noise_1", "Noise's title")
        if head is not None:
            B.click(win, head)
        W.pump(2, lambda: b.blocks.selected == "noise_1", "Noise picked")
        show = B.control(win, "blockShowOn", "Show on material ▾")
        n0 = len(D.history.changes)
        if show is not None:
            B.click(win, show)
        W.pump(0.4)
        entry = B.control(win, "menu:scale", "the menu's Scale")
        snap(screen, "1-show-menu")
        if entry is not None:
            B.click(win, entry)
        W.pump(2, lambda: noise_of(D).get("shown") == ["scale"], "Scale shown")
        chk(noise_of(D).get("shown") == ["scale"], f"Show on material › Scale: shown {noise_of(D).get('shown')}")
        chk(len(D.history.changes) == n0 + 1, "one undo step")

        # 2. back to the item's settings: the row is there; type into it
        QTest.keyClick(win, Qt.Key_Escape)
        W.pump(1.0)
        row = B.reveal(win, "row:block:noise_1:scale", "the row Noise · Scale with the material's settings")
        chk(row is not None and W.find(row, "grid:field") is not None, "the shown row has its number field")
        n0 = len(D.history.changes)
        B.type_into(win, W.find(row, "grid:field") if row is not None else None, "12", "Noise · Scale's field")
        W.pump(3, lambda: noise_of(D).get("values", {}).get("scale") == 12, "Scale 12")
        chk(noise_of(D).get("values", {}).get("scale") == 12, f"typed in the material's row: Noise Scale {noise_of(D).get('values')}")
        chk(len(D.history.changes) == n0 + 1, "one undo step")
        snap(screen, "2-shown-row")

        # 3. undo both
        QTest.keyClick(win, "z", Qt.ControlModifier)
        W.pump(0.8)
        chk(noise_of(D).get("values", {}).get("scale") != 12, "Ctrl+Z: Scale back")
        QTest.keyClick(win, "z", Qt.ControlModifier)
        W.pump(0.8)
        chk(not noise_of(D).get("shown"), "Ctrl+Z again: not shown any more")
        W.pump(0.5)
        chk(B.by_name(win, "row:block:noise_1:scale") is None, "the row is gone from the material's settings")
        snap(screen, "3-undone")
    finally:
        screen.close()
        shutil.rmtree(project, ignore_errors=True)
    fails = [c for c in B.REPORT.get("checks", []) if not c.get("ok")] if isinstance(B.REPORT.get("checks"), list) else []
    if fails or W.FAILS:
        print(f"\nfailed: {fails or W.FAILS}")
        sys.exit(1)
    print("\nevery check passed")


if __name__ == "__main__":
    main()
