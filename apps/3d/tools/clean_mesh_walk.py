# PR4 walk: Make a clean mesh by real input in the real 3D window (behind the person's work, never focused). Bridge
# calls only read state. The sample scene; Q, Lump on the ground (a clay), one Add stroke; then:
#   1. the Clay panel's Clean mesh group shows; Faces typed (a new count each run) .................................................. "1-*"
#   2. Make clean mesh clicked, Cancel clicked at once: nothing added, the clay still shown .......................... "2-*"
#   3. Make clean mesh again: the bar shows while it runs, then a new mesh of four-sided faces is selected, the clay
#      hidden, one undo step ................................................................................ "3-*"
#   4. Ctrl+Z: the mesh gone, the clay shown again; Make again: instant (the rebuild was kept) ..................... "4-*"
# Pictures to the out folder (1646 x 900). Run: <venv python> apps\3d\tools\clean_mesh_walk.py <out folder>
# Exit 0 = every check passed.
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-pr4-finish\clean")
sys.argv = sys.argv[:1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "app" / "tests"))
import clay_walk as W  # noqa: E402
import sculpt_layers_walk as L  # noqa: E402

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND, remesh  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d.sample import SOURCE  # noqa: E402

import main as app3d  # noqa: E402

W.OUT = OUT
FACES = 1500 + int(time.time()) % 1000      # a count not asked before, so the first Make really rebuilds (not the cache)


def snap(screen, name):
    W.settled_picture(screen, screen.win).save(str(OUT / f"clean-{name}.png"))
    print("picture", OUT / f"clean-{name}.png")


def meshes(doc):
    return [i for i in doc.data["items"] if i["type"] == "mesh" and i.get("shape") == "poly"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-cleanwalk-"))
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("sample.py", run_source(SOURCE, "sample.py"))
    doc.save()
    screen = app3d.Screen(W.SIZE)
    try:
        screen.show(doc, autosave=True)
        win, v = screen.win, screen.bridge.viewport
        W.pump(60, screen.ready, "the first picture")
        vp_item = W.find(win.contentItem(), "viewport3d")
        QTest.keyClick(win, Qt.Key_Q)
        W.pump(0.3)
        W.click(win, W.find(win.contentItem(), "clayMakeLump"))
        ground = vp_item.mapToScene(QPointF(vp_item.width() * 0.5, vp_item.height() * 0.8))
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, ground.toPoint())
        W.pump(20, lambda: v.clay.clayId != "", "the Lump click's new clay")
        clay_id = v.clay.clayId
        W.check(bool(clay_id), f"a Lump click made a clay ({clay_id})")
        serial = v.serial
        W.pump(30, lambda: v.serial > serial and not v.status.startswith("Error"), "the clay drawn")
        W.pump(0.5)
        W.pick_tile(win, v.clay, "Add", "add")
        L.settle(screen, clay_id)
        at, radius = W.clay_on_screen(screen, clay_id, vp_item)
        L.drag(screen, win, clay_id, at, radius * 0.6)
        L.settle(screen, clay_id)
        before = len(meshes(doc))

        # 1. the group, Faces typed
        group = W.find(win.contentItem(), "clayClean")
        W.check(group is not None and group.isVisible(), "the Clean mesh group shows with a clay selected")
        faces = W.find(win.contentItem(), "clayCleanFaces")
        W.click(win, faces)
        W.pump(0.3)
        QTest.keyClick(win, "a", Qt.ControlModifier)
        for ch in str(FACES):
            QTest.keyClick(win, ch)
        QTest.keyClick(win, Qt.Key_Return)
        W.pump(0.4)
        W.check(v.clay.cleanObj.faces == FACES, f"Faces typed {FACES} ({v.clay.cleanObj.faces})")
        snap(screen, "1-group")

        # 2. Make, then Cancel at once
        W.click(win, W.find(win.contentItem(), "clayCleanMake"))
        W.pump(0.05)
        cancel = W.find(win.contentItem(), "clayCleanCancel")
        W.check(cancel is not None and cancel.isVisible(), "while it runs the row shows Cancel")
        W.check(W.find(win.contentItem(), "clayCleanBar").isVisible(), "while it runs the row shows the bar")
        snap(screen, "2a-running")
        if cancel is not None:
            W.click(win, cancel)
        W.pump(20, lambda: not v.clay.cleanObj.running, "the cancelled job to end")
        W.pump(0.5)
        W.check(len(meshes(doc)) == before, "cancelled: no mesh added")
        W.check(doc.item(clay_id).get("visible", True) is True, "cancelled: the clay still shown")
        W.check(v.clay.cleanObj.failure == "", "cancelled: no failure line")

        # 3. Make, to the end
        t0 = time.perf_counter()
        W.click(win, W.find(win.contentItem(), "clayCleanMake"))
        W.pump(0.05)
        W.check(v.clay.cleanObj.running, "Make clean mesh: running at once")
        W.pump(120, lambda: not v.clay.cleanObj.running, "the clean mesh")
        took = time.perf_counter() - t0
        print(f"reading the clay from the engine held the window {v.clay.cleanObj.read_ms:.0f} ms; "
              f"{len(remesh._LAST.get('raw', {}).get('faceIndices', [])) // 3:,} triangles")
        made = meshes(doc)
        W.check(len(made) == before + 1, f"a new mesh was added ({len(made) - before})")
        W.check(v.clay.cleanObj.failure == "", f"no failure ({v.clay.cleanObj.failure or '-'})")
        if len(made) > before:
            m = made[-1]
            sides = set(m["faceCounts"])
            W.check(sides == {4}, f"every face has four sides ({sorted(sides)}), {len(m['faceCounts'])} faces in {took:.1f} s")
            W.check(FACES / 2 <= len(m["faceCounts"]) <= FACES * 2,
                    f"about the Faces asked for ({FACES}): {len(m['faceCounts'])}")
            W.check(screen.bridge.selection == [m["id"]] or m["id"] in str(screen.bridge.selection),
                    f"the new mesh is selected ({screen.bridge.selection})")
        W.check(doc.item(clay_id).get("visible") is False, "the clay is hidden")
        QTest.keyClick(win, Qt.Key_Escape)                # leave Clay so the picture shows the mesh plainly
        W.pump(1.0)
        L.settle(screen, clay_id)
        snap(screen, "3-mesh")

        # 4. undo, then again (kept)
        QTest.keyClick(win, "z", Qt.ControlModifier)
        W.pump(1.0)
        W.check(len(meshes(doc)) == before, "Ctrl+Z: the mesh is gone")
        W.check(doc.item(clay_id).get("visible", True) is True, "Ctrl+Z: the clay is shown again")
        screen.bridge.select(clay_id) if hasattr(screen.bridge, "select") else None
        W.pump(0.5)
        QTest.keyClick(win, Qt.Key_Q)
        W.pump(0.6)
        t0 = time.perf_counter()
        W.click(win, W.find(win.contentItem(), "clayCleanMake"))
        W.pump(60, lambda: not v.clay.cleanObj.running, "the clean mesh again")
        again = time.perf_counter() - t0
        W.check(len(meshes(doc)) == before + 1, f"made again from the kept rebuild in {again:.2f} s")
        W.check(again < took, f"the second time is quicker ({again:.2f} s vs {took:.2f} s)")
        snap(screen, "4-again")
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
