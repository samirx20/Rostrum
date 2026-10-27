# Brief 23b walk (a material as blocks): tried by real input in the real window (a background window at 1646 x 900,
# never focused): real mouse and keys (QTest) on visible controls found by objectName; the document is only READ, to
# check, never changed by bridge calls. From a new project:
#   1. Shapes › Sphere, a click on the ground: a sphere, selected ......................... "1-sphere"
#   2. its Material ▾, a starting point (Matte plastic): its own material .................. "2-material"
#   3. Edit as blocks (the material's last row): the bottom panel is the block view, Surface in it, "‹ Back · … blocks"
#      ...................................................................................... "3-blocks-open"
#   4. the add list (+ Add block), "noi" typed, Enter: a Noise block in the document ........ "4-noise-added"
#   5. a drag from Noise's value port to Surface's Roughness port: the wire in the document, one undo step
#      ...................................................................................... "5-wired"
#   6. the look menu: Quick, then Final (Cycles, waited for) ............................ "6-quick", "6-final"
#   7. a block dragged by its header (~60 moves) and a wire (Noise colour -> Surface Base colour, ~60 moves); each move
#      timed on the window thread in real ms (perf_counter_ns around the move and its events): median / p95 / max;
#      each release one undo step ......................................................... "7-dragged"
#   8. Esc: the timeline again ............................................................ "8-timeline"
# Every check, the times and the document's graph go to blocks23_walk.json in the out folder, with the pictures.
# The lead runs it:
#   heavy.ps1 run "hem: 3d-23 blocks walk" gpu <venv python> apps\3d\tools\blocks23_walk.py <out folder>
# Exit 0 = every check passed; else the failed checks are printed and it exits 1.
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-23\walk")
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_walk as W  # noqa: E402  (puts this checkout's code first; its real-input helpers)
import clay_paint_walk as CP  # noqa: E402

from PySide6.QtCore import QCoreApplication, QPoint, QPointF, Qt  # noqa: E402
from rostrum3d import graph as G  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d import files_3d  # noqa: E402

REPORT = CP.REPORT
REPORT.update({"drags": {}, "graph": {}})
chk, step, settle = CP.chk, CP.step, CP.settle
BUDGET_MS = 16.0
MOVES = 60


def qtest():
    from PySide6.QtTest import QTest
    return QTest


def by_name(win, name):
    return W.find(win.contentItem(), name)


def visible(win, item) -> bool:
    """On screen and inside every clipping ancestor (a click there lands on it)."""
    if item is None or not item.isVisible():
        return False
    p = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    if not (0 <= p.x() < win.width() and 0 <= p.y() < win.height()):
        return False
    a = item.parentItem()
    while a is not None:
        if a.clip():
            q = a.mapFromScene(p)
            if not (0 <= q.x() < a.width() and 0 <= q.y() < a.height()):
                return False
        a = a.parentItem()
    return True


def wait_for(seconds, until) -> bool:
    end = time.perf_counter() + seconds
    while not until():
        if time.perf_counter() > end:
            return False
        W.pump(0.001)
    return True


def control(win, name, what, seconds=5.0):
    """The visible control `name`, waited for; a named failed check when it isn't there."""
    wait_for(seconds, lambda: visible(win, by_name(win, name)))
    it = by_name(win, name)
    ok = visible(win, it)
    chk(ok, f"{what} is on screen ({name})")
    return it if ok else None


def click(win, item):
    W.click(win, item)


def reveal(win, name, what, scroller="inspectorScroll", tries=14):
    """The control `name` below a scrolling panel's fold: the wheel over the panel (as a person scrolls) until it
    shows; then the visible control (a named failed check when it never shows)."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QGuiApplication, QWheelEvent
    panel = by_name(win, scroller)
    for _ in range(tries):
        it = by_name(win, name)
        if it is None or visible(win, it) or panel is None:
            break
        at = panel.mapToScene(QPointF(panel.width() / 2, panel.height() / 2))
        ev = QWheelEvent(at, QPointF(win.mapToGlobal(at.toPoint())), QPoint(), QPoint(0, -120), Qt.NoButton,
                         Qt.NoModifier, Qt.NoScrollPhase, False)
        QGuiApplication.sendEvent(win, ev)
        W.pump(0.12)
    return control(win, name, what)


def type_text(win, text):
    from PySide6.QtTest import QTest
    for ch in text:
        QTest.keyClick(win, ch)
        W.pump(0.02)


def shot(win, v, name):
    CP.shot(win, v, name)


def material_of(doc, item_id):
    mid = doc.item(item_id).get("material", "") if doc.has(item_id) else ""
    return doc.item(mid) if mid and doc.has(mid) else None


def blocks_of(mat, type_=None):
    """The material's blocks (rostrum3d.graph: the material's `blocks` field holds blocks, wires and Surface's place)."""
    return [b for b in G.graph_of(mat or {})["blocks"] if type_ is None or b.get("type") == type_]


def wires_of(mat):
    return [(w.get("from"), w.get("to")) for w in G.graph_of(mat or {})["wires"]]


def pct(xs, q):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 2) if xs else None


def timed_drag(win, a: QPoint, b: QPoint, moves=MOVES, pause=0.008):
    """Press at `a`, `moves` pointer moves to `b`, release there. Each move timed on the window thread: the move and
    every event it led to, in real ms (perf_counter_ns), and the thread's own processor ms (W.gui_cycles_ms)."""
    QTest = qtest()
    QTest.mouseMove(win, a)
    W.pump(0.15)
    QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, a)
    W.pump(0.05)
    real, cpu = [], []
    for k in range(1, moves + 1):
        p = QPoint(round(a.x() + (b.x() - a.x()) * k / moves), round(a.y() + (b.y() - a.y()) * k / moves))
        c0, t0 = W.gui_cycles_ms(), time.perf_counter_ns()
        QTest.mouseMove(win, p)
        QCoreApplication.processEvents()
        real.append((time.perf_counter_ns() - t0) / 1e6)
        cpu.append(W.gui_cycles_ms() - c0)
        W.pump(pause)                       # (the frame between moves, as a hand gives it; not timed)
    QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, b)
    W.pump(0.3)
    return {"moves": len(real), "realMs": {"median": pct(real, 0.5), "p95": pct(real, 0.95), "max": pct(real, 1.0)},
            "cpuMs": {"median": pct(cpu, 0.5), "p95": pct(cpu, 0.95)}, "realMsInOrder": [round(x, 2) for x in real]}


def pick_look(win, v, look):
    btn = control(win, "viewLook", "the Camera and look button")
    if btn is None:
        return False
    click(win, btn)
    entry = control(win, f"menu:look:{look}", f"the look menu's {look.capitalize()}", 3)
    if entry is None:
        qtest().keyClick(win, Qt.Key_Escape)
        return False
    click(win, entry)
    return wait_for(10, lambda: v.look == look)


def main():
    QTest = qtest()
    OUT.mkdir(parents=True, exist_ok=True)
    CP.OUT = OUT
    project = Path(tempfile.mkdtemp(prefix="rostrum-blocks23walk-"))
    app = qt_app()  # noqa: F841
    doc = files_3d.blank(project)
    screen = W.app3d.Screen(W.SIZE)
    try:
        screen.show(doc, autosave=True)
        win, v, b = screen.win, screen.bridge.viewport, screen.bridge
        W.pump(90, screen.ready, "the first picture")
        D = b.doc
        vp = W.find(win.contentItem(), "viewport3d")
        settle(v, time.perf_counter(), what="the first settled picture")

        # 1. a sphere on the ground, selected
        step("1 sphere")
        rail = control(win, "rail_shapes", "the rail's Shapes")
        if rail is not None:
            click(win, rail)
        tile = control(win, "fly_mesh:sphere", "Shapes › Sphere")
        before = {i["id"] for i in D.items()}
        if tile is not None:
            click(win, tile)
            at = vp.mapToScene(QPointF(vp.width() * 0.5, vp.height() * 0.62)).toPoint()
            QTest.mouseMove(win, at)
            W.pump(0.3)
            QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
            W.pump(15, lambda: any(i["id"] not in before and i.get("shape") == "sphere" for i in D.items()), "the sphere")
        sphere = next((i["id"] for i in D.items() if i["id"] not in before and i.get("shape") == "sphere"), "")
        chk(bool(sphere), f"a sphere was placed ({sphere or 'none'})")
        if not sphere:
            raise RuntimeError("no sphere to give a material to")
        W.pump(5, lambda: b.selected == sphere, "the sphere selected")
        chk(b.selected == sphere, f"the new sphere is selected ({b.selected})")
        shot(win, v, "1-sphere")

        # 2. Material ▾ › a starting point
        step("2 material")
        field = control(win, "materialField", "the Material field")
        if field is not None:
            click(win, field)
        start = control(win, "matstart:matte plastic", "the picker's Matte plastic")
        if start is not None:
            click(win, start)
        W.pump(5, lambda: material_of(D, sphere) is not None, "the sphere's material")
        mat = material_of(D, sphere)
        chk(mat is not None, f"the sphere has its own material ({(mat or {}).get('id')})")
        if mat is None:
            raise RuntimeError("no material to open as blocks")
        mid = mat["id"]
        if by_name(win, "matstart:matte plastic") is not None:      # the picker still open: put it away
            QTest.keyClick(win, Qt.Key_Escape)
        W.pump(0.3)
        shot(win, v, "2-material")

        # 3. Edit as blocks
        step("3 edit as blocks")
        link = reveal(win, "editAsBlocks", "the material's Edit as blocks row")
        if link is not None:
            click(win, link)
        W.pump(5, lambda: b.blocks.open, "the block view")
        chk(b.blocks.open and b.blocks.material == mid, f"the block view shows {mid} ({b.blocks.material!r})")
        chk(control(win, "blockView", "the block view") is not None, "the bottom panel is the block view")
        chk(by_name(win, "sceneList") is None, "the timeline is put away (no visible sceneList)")
        chk(control(win, "block:surface", "the Surface block") is not None, "today's settings show as one Surface block")
        chk(control(win, "blocksBack", "‹ Back") is not None, "the header's ‹ Back is there")
        chk(CP.find_text(win.contentItem(), "· " + b.blocks.title + " blocks") is not None,
            f"the header says '· {b.blocks.title} blocks'")
        chk(control(win, "blockSettings", "the picked block's settings (Surface)") is not None, "the right panel shows Surface's settings")
        shot(win, v, "3-blocks-open")

        # 4. + Add block, "noi", Enter
        step("4 add noise")
        add = control(win, "blockAddButton", "+ Add block")
        n0 = len(D.history.changes)
        if add is not None:
            click(win, add)
        control(win, "blockAddList", "the add list")
        search = control(win, "blockAddSearch", "the add list's search")
        W.pump(0.2)
        type_text(win, "noi")
        W.pump(0.3)
        chk(control(win, "blockAddItem:noise", "Noise in the filtered list", 2) is not None, "typing 'noi' shows Noise")
        REPORT["addListAfterNoi"] = sorted(n for n in _names(win) if n.startswith("blockAddItem:"))
        QTest.keyClick(win, Qt.Key_Return)
        if not wait_for(3, lambda: bool(blocks_of(material_of(D, sphere), "noise"))):
            chk(False, "Enter in the add list adds the highlighted block (Noise)")
            item = by_name(win, "blockAddItem:noise")
            if visible(win, item):
                click(win, item)                       # the click way, so the rest of the walk can go on
        W.pump(5, lambda: bool(blocks_of(material_of(D, sphere), "noise")), "a Noise block")
        noise = (blocks_of(material_of(D, sphere), "noise") or [{}])[0].get("id", "")
        chk(bool(noise), f"a Noise block is in the document ({noise or 'none'})")
        chk(len(D.history.changes) == n0 + 1, f"adding it was one undo step ({n0} -> {len(D.history.changes)})")
        chk(search is None or not search.isVisible(), "the add list closed")
        if not noise:
            raise RuntimeError("no Noise block to wire")
        W.pump(0.5)
        if not (visible(win, by_name(win, f"port:{noise}:out:value")) and visible(win, by_name(win, "port:surface:in:roughness"))):
            REPORT["fitPressed"] = True
            QTest.keyClick(win, Qt.Key_F)              # F fits every block in the view
            W.pump(0.6)
        shot(win, v, "4-noise-added")

        # 5. Noise value -> Surface Roughness, by a real drag
        step("5 wire")
        out_port = control(win, f"port:{noise}:out:value", "Noise's value port")
        in_port = control(win, "port:surface:in:roughness", "Surface's Roughness port")
        n0 = len(D.history.changes)
        if out_port is not None and in_port is not None:
            REPORT["drags"]["firstWire"] = timed_drag(win, W.centre(out_port), W.centre(in_port), moves=24)
        W.pump(5, lambda: (f"{noise}.value", "surface.roughness") in wires_of(material_of(D, sphere)), "the wire")
        wires = wires_of(material_of(D, sphere))
        chk((f"{noise}.value", "surface.roughness") in wires, f"the document has the wire {noise}.value -> surface.roughness ({wires})")
        chk(len(D.history.changes) == n0 + 1, f"the wire was one undo step ({n0} -> {len(D.history.changes)})")
        head = control(win, "blockHeader:surface", "Surface's header")
        if head is not None:
            click(win, head)                     # Surface picked: its settings (the material's rows) on the right
        W.pump(2, lambda: b.blocks.selected == "surface", "Surface picked")
        chk(b.blocks.selected == "surface", f"a click on Surface's title picks it ({b.blocks.selected})")
        panel = by_name(win, "blockSettings")
        rough = W.find(panel, "row:roughness") if panel is not None else None
        chk(rough is not None and CP.find_text(rough, "Set by a wire") is not None, "Surface's Roughness row says a wire sets it")
        shot(win, v, "5-wired")

        # 6. Quick, then Final
        step("6 looks")
        chk(pick_look(win, v, "quick"), f"the look menu's Quick ({v.look})")
        W.pump(0.5)
        chk(not v.status.startswith("Error") and not b.status.startswith("Error"), f"Quick draws the blocks ({v.status or b.status or '-'})")
        shot(win, v, "6-quick")
        t0 = time.perf_counter()
        chk(pick_look(win, v, "final"), f"the look menu's Final ({v.look})")
        W.pump(240, lambda: v.look == "final" and (v.final.fraction >= 0.5 or v.finalLine.startswith("Final · done")),
               "Final to converge")
        REPORT["timesMs"]["final-converge"] = round((time.perf_counter() - t0) * 1000)
        chk(v.look == "final" and not v.status.startswith("Error"), f"Final draws the blocks ({v.finalLine})")
        QTest.mouseMove(win, QPoint(8, 8))
        W.pump(0.5)
        path = OUT / "6-final.png"
        win.grabWindow().save(str(path))
        REPORT["pictures"]["6-final"] = str(path)
        pick_look(win, v, "quick")

        # 7. a block drag and a wire drag, timed per move
        step("7 drags")
        header = control(win, f"blockHeader:{noise}", "Noise's header")
        x0 = next((bl.get("x") for bl in blocks_of(material_of(D, sphere)) if bl["id"] == noise), None)
        n0 = len(D.history.changes)
        if header is not None:
            a = W.centre(header)
            REPORT["drags"]["block"] = r = timed_drag(win, a, QPoint(a.x() - 120, a.y() + 30))
            chk(r["moves"] >= MOVES, f"{MOVES} moves in the block drag ({r['moves']})")
            chk(r["realMs"]["p95"] is not None and r["realMs"]["p95"] < BUDGET_MS,
                f"a block drag move within {BUDGET_MS:g} ms real (median {r['realMs']['median']}, p95 {r['realMs']['p95']} ms)")
        W.pump(3, lambda: len(D.history.changes) > n0, "the block move's change")
        x1 = next((bl.get("x") for bl in blocks_of(material_of(D, sphere)) if bl["id"] == noise), None)
        chk(x1 is not None and x0 is not None and x1 != x0, f"the block moved in the document (x {x0} -> {x1})")
        chk(len(D.history.changes) == n0 + 1, f"the block move was one undo step ({n0} -> {len(D.history.changes)})")
        W.pump(0.5)
        out_port = control(win, f"port:{noise}:out:colour", "Noise's colour port")
        in_port = control(win, "port:surface:in:baseColor", "Surface's Base colour port")
        n0 = len(D.history.changes)
        if out_port is not None and in_port is not None:
            REPORT["drags"]["wire"] = r = timed_drag(win, W.centre(out_port), W.centre(in_port))
            chk(r["moves"] >= MOVES, f"{MOVES} moves in the wire drag ({r['moves']})")
            chk(r["realMs"]["p95"] is not None and r["realMs"]["p95"] < BUDGET_MS,
                f"a wire drag move within {BUDGET_MS:g} ms real (median {r['realMs']['median']}, p95 {r['realMs']['p95']} ms)")
        W.pump(3, lambda: (f"{noise}.colour", "surface.baseColor") in wires_of(material_of(D, sphere)), "the second wire")
        chk((f"{noise}.colour", "surface.baseColor") in wires_of(material_of(D, sphere)),
            f"the second wire is in the document ({wires_of(material_of(D, sphere))})")
        chk(len(D.history.changes) == n0 + 1, f"the second wire was one undo step ({n0} -> {len(D.history.changes)})")
        shot(win, v, "7-dragged")

        # 8. Esc: the timeline again
        step("8 esc")
        view = by_name(win, "blockView")
        REPORT["keysInBlockView"] = bool(view is not None and view.hasActiveFocus())   # (the drags gave it the keyboard)
        QTest.mouseMove(win, QPoint(8, 8))
        QTest.keyClick(win, Qt.Key_Escape)
        W.pump(3, lambda: not b.blocks.open, "Esc to close the block view")
        chk(not b.blocks.open, "Esc closes the block view")
        chk(control(win, "sceneList", "the timeline's scene list", 2) is not None,
            "the timeline is back")
        chk(b.selected == sphere, f"the sphere is still selected ({b.selected})")
        shot(win, v, "8-timeline")
        REPORT["graph"] = G.graph_of(material_of(D, sphere) or {})
        REPORT["graphProblems"] = G.problems(material_of(D, sphere) or {})
        chk(not REPORT["graphProblems"], f"the graph has no problems ({REPORT['graphProblems']})")
    except Exception as e:                   # a step that could not go on: named in the report, never a silent stop
        W.FAILS.append(f"the walk stopped in step {CP.CURRENT[0]!r}: {e!r}")
        raise
    finally:
        REPORT["fails"] = list(W.FAILS)
        (OUT / "blocks23_walk.json").write_text(json.dumps(REPORT, indent=2, default=str), encoding="utf-8")
        screen.close() if hasattr(screen, "close") else None
    print("FAILS:" if W.FAILS else "ALL PASSED", *W.FAILS, sep="\n  ")
    sys.exit(1 if W.FAILS else 0)


def _names(win):
    out = []

    def walk(it):
        for c in it.childItems():
            if c.isVisible() and c.objectName():
                out.append(c.objectName())
            walk(c)
    walk(win.contentItem())
    return out


if __name__ == "__main__":
    main()
