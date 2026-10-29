# PR4 walk: sculpt layers by real input in the real 3D window (behind the person's work, never focused). Bridge calls
# only read state. The sample scene; Q, Lump on the ground (a clay); then:
#   1. a real click on the Steps head's "+ Layer": the Layers list shows Base and Layer 1, chosen ............ "1-*"
#   2. an Add stroke dragged across the clay: its step is on the layer; the clay changed ........................ "2-*"
#   3. the layer's Amount typed 0 %: the clay is back to the Base's shape (same hash as before the stroke) .... "3-*"
#   4. Amount 60 %: a shape between; the eye clicked: off = the Base again; the eye again: back ................ "4-*"
#   5. Base clicked: the next stroke goes on the Base; Layer ▾ › Bake into Base: the layer goes, the shape stays ...... "5-*"
# Pictures to the out folder (1646 x 900). Run: <venv python> apps\3d\tools\sculpt_layers_walk.py <out folder>
# Exit 0 = every check passed.
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-pr3-left-pr4\layers")
sys.argv = sys.argv[:1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "app" / "tests"))
import clay_walk as W  # noqa: E402
import copies_walk as CW  # noqa: E402

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d.sample import SOURCE  # noqa: E402

import main as app3d  # noqa: E402

W.OUT = OUT


def snap(screen, name):
    W.settled_picture(screen, screen.win).save(str(OUT / f"layers-{name}.png"))
    print("picture", OUT / f"layers-{name}.png")


def settle(screen, clay_id, before=None):
    """The picture settled; the clay's hash (a different one than `before` when given)."""
    v = screen.bridge.viewport
    W.pump(30, lambda: v._r.idle() and not v._next.isActive(), "the picture to settle")
    if before is not None:
        W.pump(20, lambda: W.clay_info(v, clay_id).get("hash") != before, "the clay's new shape")
    return W.clay_info(v, clay_id).get("hash")


def drag(screen, win, clay_id, at, r):
    """One real left drag across the clay's middle; its step landed."""
    doc, before = screen.bridge.doc, len(screen.bridge.doc.item(clay_id)["steps"])
    start = QPoint(round(at.x() - r), round(at.y()))
    QTest.mouseMove(win, start)
    W.pump(0.3)
    QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, start)
    W.pump(0.3)
    for i in range(1, 25):
        p = QPoint(round(at.x() - r + 2 * r * i / 24), round(at.y() + (3 if i % 2 else 0)))
        QTest.mouseMove(win, p)
        W.pump(0.03)
    QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, p)
    W.pump(10, lambda: len(doc.item(clay_id)["steps"]) > before, "the stroke's step")
    W.check(len(doc.item(clay_id)["steps"]) == before + 1, "a real drag made one stroke step")


def type_amount(win, percent):
    rows = W.find(win.contentItem(), "clayLayerRows")
    row = W.find(W.find(win.contentItem(), "clayLayers"), "row:amount")
    W.check(row is not None and row.isVisible(), "the chosen layer's Amount row is on screen")
    box, stack = None, [row] if row is not None else []
    while stack:                                   # the percent row's number box (beside its slider)
        it = stack.pop()
        if "NumberField" in it.metaObject().className() and it.isVisible():
            box = it
            break
        stack += it.childItems()
    W.check(box is not None, "the Amount row's number box is on screen")
    W.click(win, box)
    W.pump(0.3)
    QTest.keyClick(win, "a", Qt.ControlModifier)
    for ch in str(percent):
        QTest.keyClick(win, ch)
    QTest.keyClick(win, Qt.Key_Return)
    W.pump(0.6)
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-layerswalk-"))
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
        core = W.K32.OpenProcess(0x1000, False, W.core_pid(v, v.sent()[0]))
        QTest.keyClick(win, Qt.Key_Q)
        W.pump(0.3)
        W.click(win, W.find(win.contentItem(), "clayMakeLump"))
        ground = vp_item.mapToScene(QPointF(vp_item.width() * 0.5, vp_item.height() * 0.85))
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, ground.toPoint())
        W.pump(20, lambda: v.clay.clayId != "", "the Lump click's new clay")
        clay_id = v.clay.clayId
        W.check(bool(clay_id), f"a Lump click made a clay ({clay_id})")
        serial = v.serial
        W.pump(30, lambda: v.serial > serial and not v.status.startswith("Error"), "the clay drawn")
        W.pump(0.5)
        W.pick_tile(win, v.clay, "Add", "add")
        base = settle(screen, clay_id)
        group = W.find(win.contentItem(), "clayLayers")
        W.check(group is None or not group.isVisible(), "no Layers group before a layer is made")

        # 1. + Layer
        W.click(win, W.find(win.contentItem(), "clayLayerAdd"))
        W.pump(0.6)
        lays = doc.item(clay_id).get("sculptLayers") or []
        W.check(len(lays) == 1 and doc.item(clay_id)["sculptLayer"] == lays[0]["id"],
                f"+ Layer made Layer 1 and the next strokes go on it ({[x['id'] for x in lays]})")
        W.check(W.find(win.contentItem(), "clayLayers").isVisible(), "the Layers group shows")
        lay = lays[0]["id"] if lays else ""
        snap(screen, "1-new-layer")

        # 2. a stroke on the layer
        at, radius = W.clay_on_screen(screen, clay_id, vp_item)
        drag(screen, win, clay_id, at, radius * 0.6)
        step = doc.item(clay_id)["steps"][-1]
        W.check(step.get("layer") == lay, f"the stroke's step is on the layer ({step.get('layer')!r})")
        full = settle(screen, clay_id, base)
        W.check(full != base, "the stroke changed the clay")
        snap(screen, "2-stroke-on-layer")

        # 3. Amount 0
        type_amount(win, 0)
        W.check(doc.item(lay)["amount"] == 0, f"Amount typed 0 % ({doc.item(lay)['amount']})")
        none = settle(screen, clay_id, full)
        W.check(none == base, f"at 0 % the clay is the Base's shape again ({none} vs {base})")
        snap(screen, "3-amount-0")

        # 4. 60 %, then the eye
        type_amount(win, 60)
        W.check(abs(doc.item(lay)["amount"] - 0.6) < 1e-9, f"Amount typed 60 % ({doc.item(lay)['amount']})")
        part = settle(screen, clay_id, none)
        W.check(part not in (base, full), "at 60 % a shape between")
        snap(screen, "4a-amount-60")
        W.click(win, W.find(win.contentItem(), "clayLayerEye1"))
        W.pump(0.6)
        W.check(doc.item(lay)["on"] is False, "the eye switched the layer off")
        off = settle(screen, clay_id, part)
        W.check(off == base, "off: the Base's shape")
        snap(screen, "4b-layer-off")
        W.click(win, W.find(win.contentItem(), "clayLayerEye1"))
        W.pump(0.6)
        W.check(settle(screen, clay_id, off) == part, "on again: the 60 % shape")

        # 5. Base, then Bake
        W.click(win, W.find(win.contentItem(), "clayLayer0"))
        W.pump(0.6)
        W.check(doc.item(clay_id)["sculptLayer"] == "", "a click on Base: the next stroke goes on the Base")
        W.click(win, W.find(win.contentItem(), "clayLayer1"))
        W.pump(0.6)
        more = W.find(win.contentItem(), "clayLayerMore")
        W.click(win, more)
        W.pump(0.6)
        entry = W.find(win.contentItem(), "menu:bake")
        W.check(entry is not None and entry.isVisible(), "the Layer ▾ menu shows Bake into Base")
        if entry is not None:
            W.click(win, entry)
        W.pump(0.8)
        W.check(not doc.item(clay_id).get("sculptLayers"), "Bake into Base: the layer is gone")
        W.check(settle(screen, clay_id) == part, "baked: the clay keeps the shape it showed")
        snap(screen, "5-baked")
        W.check(not v.status.startswith("Error"), f"no viewport error ({v.status or '-'})")
        W.K32.CloseHandle(W.ct.c_void_p(core))
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
