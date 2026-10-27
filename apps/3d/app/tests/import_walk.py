# Import walk (brief 29b): importing tried by real input in the real window (behind the person's work, never focused).
# A scratch project with the sample scene and two small files written next to it: a USD toy in centimetres (a body and a
# head) and an OBJ cube (no unit). By real keys and mouse (bridge calls only read state to check it):
#   1. Ctrl+I: the Import group opens on the Build page: glTF / GLB…, OBJ…, FBX…, Alembic…, USD…, Asset library.
#   2. A real click on the rail's Import button, then on USD…: the file dialog opens filtered to USD (Qt's own dialog
#      inside the window here, so nothing comes up in front of the person); it is answered with the toy (the dialog's
#      own file list is Qt's, not ours). The toy lands in the middle of the view: ONE undo step, selected, the tool
#      Select, the status says "Imported at 1/100: it was in centimetres", Keep original size shows in the panel, the
#      scene list has its two parts.
#   3. A real click on Keep original size: one undo step, fileUnit back to 1, the scale 100 times bigger, the link gone.
#   4. A real click on the Head part's scene row: the part is selected, the panel shows its Material field and Visible.
#   5. A drag from Explorer, sent as the window gets one (drag enter, moves, drop) at a viewport point: while it hovers
#      the landing ring follows the pointer; dropped, the cube lands there: one undo step, selected. A .txt dragged over
#      is refused (no ring, nothing in history).
# Pictures after each step go to the out folder. Not collected by pytest (needs the core built with brief 29's
# importers and a GPU slot); the lead runs it:
#   heavy.ps1 run "hem: import walk" gpu <venv python> apps\3d\app\tests\import_walk.py --out <folder>
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

from PySide6.QtCore import QCoreApplication, QMetaObject, QMimeData, QObject, QPoint, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d.layout_states import TOY_USDA  # noqa: E402
from screen3d.sample import SOURCE  # noqa: E402

import main as app3d  # noqa: E402

SIZE = (1646, 900)
CUBE_OBJ = "".join(f"v {x} {y} {z}\n" for x in (-0.1, 0.1) for y in (0, 0.2) for z in (-0.1, 0.1)) + (
    "f 1 3 4 2\nf 5 6 8 7\nf 1 2 6 5\nf 3 7 8 4\nf 1 5 7 3\nf 2 4 8 6\n")


def changes(doc):
    return len(doc.history.changes)


def imports(doc):
    return [i["id"] for i in doc.items() if i.get("type") == "import"]


class Walk:
    def __init__(self, screen, out):
        self.s, self.out = screen, out
        self.win, self.b, self.v = screen.win, screen.bridge, screen.bridge.viewport
        self.vp = W.find(self.win.contentItem(), "viewport3d")

    def at(self, part):
        top = self.vp.mapToScene(QPointF(0, 0))
        return QPoint(round(top.x() + part[0] * self.vp.width()), round(top.y() + part[1] * self.vp.height()))

    def snap(self, name):
        W.pump(30, lambda: self.s.ready(), f"{name}: the picture")
        W.pump(0.3)
        self.win.grabWindow().save(str(self.out / f"import-walk-{name}.png"))

    def item(self, name):
        found = W.find(self.win.contentItem(), name)
        W.check(found is not None, f"'{name}' is on screen")
        return found

    def landed(self, what, n0, before):
        W.pump(30, lambda: len(imports(self.b.doc)) > len(before) or self.b.status.startswith("Error"), f"{what}: the import")
        new = [i for i in imports(self.b.doc) if i not in before]
        W.check(len(new) == 1, f"{what}: one new import ({new}; status {self.b.status!r})")
        W.check(changes(self.b.doc) == n0 + 1, f"{what}: one undo step ({n0} -> {changes(self.b.doc)})")
        if new:
            W.check(self.b.selected == new[0], f"{what}: the new import is selected ({self.b.selected})")
        W.check(not self.b.add.armed and not self.v.clay.on and not self.v.pose.on, f"{what}: the tool is Select")
        return new[0] if new else ""

    def drag(self, path, part, drop=True):
        """A file dragged from Explorer onto the window at the viewport point `part`: enter, moves, then drop (or carried
        away again); whether the landing ring showed under the pointer."""
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(path))])
        p = self.at(part)
        steps = [QPointF(p.x() - 30, p.y() - 20), QPointF(p.x() - 10, p.y() - 5), QPointF(p)]
        enter = QDragEnterEvent(steps[0].toPoint(), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        QCoreApplication.sendEvent(self.win, enter)
        for s in steps[1:]:
            QCoreApplication.sendEvent(self.win, QDragMoveEvent(s.toPoint(), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
            W.pump(0.05)
        spot = W.find(self.win.contentItem(), "importDropSpot")
        hover = spot is not None and abs(spot.mapToScene(QPointF(spot.width() / 2, spot.height() / 2)).x() - p.x()) <= 2
        if drop:
            QCoreApplication.sendEvent(self.win, QDropEvent(QPointF(p), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
        else:                                           # carried away again
            QCoreApplication.sendEvent(self.win, QDragLeaveEvent())
        W.pump(0.2)
        return hover


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--out", default=r"C:\Users\Sam\.rostrum\waves\results\3d-29b\hem")
    out = Path(a.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-importwalk-"))
    files = project / "files"
    files.mkdir()
    (files / "toy.usda").write_text(TOY_USDA, encoding="utf-8")
    (files / "cube.obj").write_text(CUBE_OBJ, encoding="utf-8")
    (files / "notes.txt").write_text("not a 3D file\n", encoding="utf-8")
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("sample.py", run_source(SOURCE, "sample.py"))
    doc.save()
    screen = app3d.Screen(SIZE)
    try:
        screen.show(doc, autosave=True)
        w = Walk(screen, out)
        b, win = w.b, w.win
        W.pump(60, screen.ready, "the first picture")

        # 1. Ctrl+I opens the Import group
        QTest.keyClick(win, Qt.Key_I, Qt.ControlModifier)
        W.pump(0.4)
        for name in ("glTF", "OBJ", "FBX", "Alembic", "USD", "library"):
            w.item(f"fly_import:{name}")
        w.snap("1-menu")
        QTest.keyClick(win, Qt.Key_Escape)
        W.pump(0.3)

        # 2. the rail's button, USD…, the dialog answered with the toy
        files_item = win.findChild(QObject, "importFiles")
        W.check(files_item is not None, "the Import group's file picker is there")
        files_item.setProperty("useNative", False)
        W.click(win, w.item("rail_import"))
        W.pump(0.3)
        W.click(win, w.item("fly_import:USD"))
        W.pump(0.5)
        dialog = win.findChild(QObject, "importDialog")
        W.check(dialog is not None and dialog.property("visible"), "USD… opens the file dialog")
        filters = dialog.property("nameFilters") if dialog is not None else []
        W.check(list(filters) == ["USD (*.usd *.usda *.usdc *.usdz)"], f"the dialog shows only USD files ({filters})")
        w.snap("2-dialog")
        n0, before = changes(doc), imports(doc)
        dialog.setProperty("selectedFile", QUrl.fromLocalFile(str(files / "toy.usda")))
        QMetaObject.invokeMethod(dialog, "accept")
        toy = w.landed("USD… toy", n0, before)
        W.check(b.status.startswith("Imported at 1/100") and "centimetres" in b.status, f"the unit message ({b.status!r})")
        keep = W.find(win.contentItem(), "importKeepSize")
        W.check(keep is not None, "Keep original size shows in the panel")
        W.check(len(doc.item(toy).get("parts", [])) == 2, f"the toy's two parts are listed ({doc.item(toy).get('parts', [])})")
        w.snap("2-landed")

        # 3. Keep original size
        sy0 = doc.item(toy).get("sy", 1.0)
        n0 = changes(doc)
        if keep is not None:
            W.click(win, keep)
        W.pump(5, lambda: changes(doc) > n0, "Keep original size")
        W.check(changes(doc) == n0 + 1, f"Keep original size: one undo step ({n0} -> {changes(doc)})")
        it = doc.item(toy)
        W.check(abs(it.get("fileUnit", 1.0) - 1.0) < 1e-9 and abs(it.get("sy", 1.0) - sy0 * 100) < 1e-6,
                f"the toy is back to the file's numbers (fileUnit {it.get('fileUnit')}, sy {sy0} -> {it.get('sy')})")
        W.pump(0.3)
        W.check(W.find(win.contentItem(), "importKeepSize") is None, "Keep original size is gone after it ran")
        w.snap("3-kept")

        # 4. a part's scene row
        head = next((p["id"] for p in doc.item(toy).get("parts", []) if p.get("path", "").endswith("Head")), "")
        row = W.find(win.contentItem(), f"sceneRow:{head}")
        W.check(row is not None, f"the Head part has its scene row ({head})")
        if row is not None:
            W.click(win, row)
        W.check(b.selected == head, f"clicking the part's row selects it ({b.selected})")
        W.pump(0.3)
        w.item("materialField")
        w.item("row:visible")
        w.snap("4-part")

        # 5. a drag from Explorer
        n0, before = changes(doc), imports(doc)
        hover = w.drag(files / "notes.txt", (0.3, 0.7), drop=False)
        W.check(not hover and changes(doc) == n0, "a .txt dragged over is refused: no ring, nothing in history")
        n0, before = changes(doc), imports(doc)
        hover = w.drag(files / "cube.obj", (0.3, 0.7), drop=False)
        W.check(hover, "while the cube hovers, the landing ring follows the pointer")
        w.snap("5-hover")
        w.drag(files / "cube.obj", (0.3, 0.7))
        w.landed("dropped cube", n0, before)
        W.check(not b.status.startswith("Imported at"), f"an OBJ (no unit) says no unit message ({b.status!r})")
        w.snap("5-dropped")
        W.check(not w.v.status.startswith("Error"), f"no viewport error ({w.v.status or '-'})")
    finally:
        screen.close()
        app.processEvents()
        shutil.rmtree(project, ignore_errors=True)
    if W.FAILS:
        print(f"\n{len(W.FAILS)} check(s) failed")
        sys.exit(1)
    print("\nevery check passed")


if __name__ == "__main__":
    main()
