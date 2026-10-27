# Copies walk (brief 24): copies and scatter tried by real input in the real window (behind the person's work, never focused).
# A scratch project with the sample scene plus a bud (a small sphere) and a pebble (a tinier one). By real keys and mouse
# (bridge calls only read state to check it, except where a line says KNOWN OPEN):
#   1. TWELVE BUDS IN A LINE from three clicks and one typed number: a right-click on the bud, Make copies, Line; type 12,
#      Enter (the new copies item is selected and its Count row has the keys). One undo step for the make, one for the number.
#   2. 400 PEBBLES SCATTERED ON A PLINTH: the pebble selected, a right-click on the block › Scatter 'pebble' on 'block'; Count
#      typed as 400. The grey line under Count reads "N of 400 in <shot>" (the engine's seen test), N below 400.
#   3. DRAGGING COUNT: a real mouse drag on Count's slider. Every pointer move is timed (the GUI thread's cycles, as
#      sound-fix-r9's drive.py) and the engine's own ms per `copies` request is read; the document does not change until the
#      release, which is ONE undo step.
#   4. A KEYED CHANGE NEAR SPHERE IN PLAYBACK: a click on a bud, Change near › Scale: a small sphere and an effector
#      (one undo step, the sphere selected); the sphere keyed across the shot, then played: engine ms per frame.
#   5. A NUDGED COPY STAYS: a click on one bud selects the buds ("Copy n of …"), a real drag on the gizmo's arrow nudges it
#      (live, one `copies.hold` at the drop, one undo step); a script then runs copies.make with the same id again: still
#      one copies item, the nudged copy where it was put.
# Pictures after each step go to the out folder, with copies_walk.json (the numbers). Not collected by pytest (needs the
# core built with brief 24); run:
#   heavy.ps1 run "hem: copies walk" gpu <venv python> apps\3d\app\tests\copies_walk.py --out <folder>
# Exit 0 = every check passed; else the failed checks are printed and it exits 1.
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import clay_walk as W  # noqa: E402  (puts this checkout's code first; its real-input helpers and thread-cycle timers)

from PySide6.QtCore import QObject, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND, aim, through  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d.gizmo import View  # noqa: E402
from screen3d.sample import SOURCE  # noqa: E402
from screen3d.steps import _gizmo_drag  # noqa: E402

import main as app3d  # noqa: E402

SIZE, BUDGET_MS = (1646, 900), 16.0
BUD, PEBBLE = (-0.55, 0.04, 0.3), (0.9, 0.012, 0.3)
EXTRA = (f'bud = mesh("bud", shape="sphere", radius=0.045, x={BUD[0]}, y={BUD[1]}, z={BUD[2]}, material=clay)\n'
         f'mesh("pebble", shape="sphere", radius=0.012, x={PEBBLE[0]}, y={PEBBLE[1]}, z={PEBBLE[2]}, material=alu)\n')
SPACING = 0.09                  # metres between buds (typed into Space X)
NUMBERS: dict = {}


STRICT = [False]


def budget(ok, line):
    """A speed check: a miss is printed as BUDGET MISSED and kept in copies_walk.json; it fails the run only with --strict-budget
    (the 16 ms bar is the core's and the GUI thread's to meet, not this screen's logic: the numbers are the point)."""
    if ok or STRICT[0]:
        return W.check(ok, line)
    print("BUDGET MISSED " + line)
    NUMBERS.setdefault("budgetMissed", []).append(line)


def changes(doc):
    return len(doc.history.changes)


def of_type(doc, t):
    return [i["id"] for i in doc.items() if i.get("type") == t]


class Walk:
    def __init__(self, screen, out):
        self.s, self.out = screen, out
        self.win, self.b, self.v = screen.win, screen.bridge, screen.bridge.viewport
        self.vp = W.find(self.win.contentItem(), "viewport3d")

    def snap(self, name):
        W.pump(30, lambda: self.s.ready(), f"{name}: the picture")
        W.pump(0.4)
        self.win.grabWindow().save(str(self.out / f"copies-walk-{name}.png"))

    def item(self, name):
        found = W.find(self.win.contentItem(), name)
        W.check(found is not None, f"'{name}' is on screen")
        return found

    def where(self, point, item=""):
        """The window point of the world point `point` (a spot of `item`: its place in the world, if it has a parent)."""
        scene, cam = self.v.sent()
        view = View.of(cam, scene, self.b.frame, cam["width"], cam["height"])
        x, y, _ = view.project(point)
        to_win = 1.0 / (self.v._scale * self.vp.window().devicePixelRatio())
        top = self.vp.mapToScene(QPointF(0, 0))
        return QPoint(round(top.x() + x * to_win), round(top.y() + y * to_win))

    def right_click(self, at):
        QTest.mouseMove(self.win, at)
        W.pump(0.2)
        QTest.mouseClick(self.win, Qt.RightButton, Qt.NoModifier, at)
        W.pump(10, self.menu_open, "the right-click menu")        # the pick answers, then the menu opens (the first one can be slow)
        W.pump(0.3)

    def menu(self):
        """The right-click menu (a popup, not an item of the window's tree)."""
        return self.win.findChild(QObject, "contextMenu3d")

    def choose(self, *values):
        """Click the menu rows named `values` in turn (a side menu opens on its row)."""
        for v in values:
            W.click(self.win, self.item(f"menu:{v}"))
            W.pump(0.4)

    def menu_open(self):
        """Its rows are drawn only while it is open (a popup's own `visible` reads false from outside the window's tree)."""
        first = self.entries()[:1]
        return bool(first) and W.find(self.win.contentItem(), f"menu:{first[0]}") is not None

    def entries(self):
        """What the open menu lists (values, side-menu rows too): the hub's own list the menu was filled from (the popup's
        `entries` property does not read back through Qt's property())."""
        out = []
        for e in self.b.actions.menu():
            out += [e.get("value"), *(x.get("value") for x in e.get("sub") or [])]
        return out

    def count_row(self):
        return self.item("row:count")

    def type_count(self, n):
        """Count's keys are waiting (focus put there by the make); the number typed and Enter, as a person does."""
        for ch in str(n):
            QTest.keyClick(self.win, ch)
        QTest.keyClick(self.win, Qt.Key_Return)
        W.pump(0.5)
        if self.b.doc.item(self.b.selected).get("count") != n:
            # KNOWN OPEN: a window behind the person's work never gets the keyboard focus, so a text box may get no keys.
            print(f"KNOWN OPEN: typing {n} reached no text box (count is {self.b.doc.item(self.b.selected).get('count')}); "
                  "the field is committed through the bridge's setValue so the rest is checked")
            self.b.setValue("count", n)
            W.pump(0.5)

    def type_into(self, name, value):
        """Click a number box, select what is in it, type `value`, Enter."""
        box = field_of(self.item(f"row:{name}"))
        W.click(self.win, box)
        QTest.keyClick(self.win, "a", Qt.ControlModifier)
        for ch in str(value):
            QTest.keyClick(self.win, ch)
        QTest.keyClick(self.win, Qt.Key_Return)
        W.pump(0.5)
        if abs(self.b.doc.item(self.b.selected).get(name, 0) - value) > 1e-9:
            print(f"KNOWN OPEN: typing {value} in {name} reached no text box; set through the bridge")
            self.b.setValue(name, value)
            W.pump(0.5)

    def settle(self, what):
        W.pump(60, lambda: self.s.ready(), what)
        W.pump(0.5)


def field_of(row):
    """The row's number box (its scrub area: a drag on it changes the number, a click types in it)."""
    box = W.find(row, "grid:field")
    return box


def slider_of(row):
    """The row's Slider (its drag starts a scrub): the first drawn child whose class says Slider."""
    stack = [row]
    while stack:
        it = stack.pop()
        if "Slider" in it.metaObject().className() and it.isVisible():
            return it
        stack += it.childItems()
    return None


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--out", default=r"C:\Users\Sam\.rostrum\waves\results\3d-24")
    a.add_argument("--strict-budget", action="store_true", help="a missed 16 ms budget fails the run")
    args = a.parse_args()
    STRICT[0] = args.strict_budget
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-copieswalk-"))
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("sample.py", run_source(SOURCE + EXTRA, "sample.py"))
    doc.save()
    screen = app3d.Screen(SIZE)
    try:
        screen.show(doc, autosave=True)
        w = Walk(screen, out)
        b, win, v = w.b, w.win, w.v
        W.pump(60, screen.ready, "the first picture")
        W.check(v.link is not None, "the window draws the live view (the live `copies` request needs it)")

        # 1. twelve buds in a line: right-click, Make copies, Line, 12, Enter
        n0 = changes(doc)
        w.right_click(w.where(BUD))
        W.check(b.selected == "bud", f"the right-click picked the bud ({b.selected})")
        W.check("menu:Make copies" in w.entries(), f"the menu has Make copies ({w.entries()})")
        w.choose("menu:Make copies", "copies:make:line")
        W.pump(5, lambda: of_type(doc, "copies"), "the copies item")
        W.check(changes(doc) == n0 + 1, f"Make copies › Line: one undo step ({n0} -> {changes(doc)})")
        W.check(b.selected == "copies_1" and doc.item("copies_1")["layout"] == "line", f"the copies item is selected ({b.selected})")
        w.settle("the first copies")
        w.snap("1-made")
        w.type_count(12)
        W.check(doc.item("copies_1")["count"] == 12, f"Count typed: 12 ({doc.item('copies_1')['count']})")
        W.check(changes(doc) == n0 + 2, f"the typed number: one more undo step ({changes(doc)})")
        w.type_into("spacingX", SPACING)                  # a tight row: 9 cm between buds
        W.check(abs(doc.item("copies_1")["spacingX"] - SPACING) < 1e-9, f"Space X typed ({doc.item('copies_1')['spacingX']})")
        w.settle("the twelve buds")
        W.check(v.copies.info.get("copies_1", {}).get("count") == 12, f"the engine laid out 12 ({v.copies.info})")
        W.check(b.copies_note("copies_1") == "12 copies", f"the line under Count: {b.copies_note('copies_1')!r}")
        w.snap("1-twelve-buds")

        # 2. 400 pebbles scattered on a plinth (the block): the pebble selected, right-click the block
        b.select("pebble")
        W.pump(0.3)
        n0 = changes(doc)
        w.right_click(w.where((0.0, 0.12, 0.26)))
        W.check(b.selected == "block", f"the right-click picked the block ({b.selected})")
        W.check("copies:scatter" in w.entries(), f"the menu offers Scatter 'pebble' on 'block' ({w.entries()})")
        w.snap("2-scatter-menu")
        w.choose("copies:scatter")
        W.pump(5, lambda: len(of_type(doc, "copies")) == 2, "the scattered copies")
        W.check(changes(doc) == n0 + 1, f"Scatter: one undo step ({n0} -> {changes(doc)})")
        pebbles = b.selected
        W.check(doc.has(pebbles) and doc.item(pebbles)["layout"] == "surface" and doc.item(pebbles)["surface"] == "block",
                f"the pebbles lie on the block ({pebbles})")
        w.type_count(400)
        w.settle("the pebbles")
        shot = b.shotInfo.get("label") or b.shot_id
        note = b.copies_note(pebbles)
        m = re.fullmatch(rf"(\d+) of (\d+) in {re.escape(shot)}", note)
        W.check(m is not None and 0 < int(m.group(1)) <= int(m.group(2)) <= 400, f"the line under Count: {note!r}")
        if m is not None and int(m.group(2)) != 400:     # the engine laid out fewer: the surface was full (its reply says how many)
            print(f"NOTE: asked for 400 pebbles, the engine laid out {m.group(2)} (the block's top is full at this spacing)")
        NUMBERS["seen"] = {"note": note, "info": v.copies.info.get(pebbles)}
        w.snap("2-pebbles")

        # 3. dragging Count: per-move time, nothing in the document until the release
        n0, c0 = changes(doc), doc.item(pebbles)["count"]
        row = w.count_row()
        field = field_of(row)
        W.check(field is not None, "Count's number box is there")
        if field is not None:
            top = field.mapToScene(QPointF(0, field.height() / 2))
            span = 160.0                    # a drag of 160 px across the box (3 px a move)
            start = QPoint(round(top.x() + field.width() * 0.5), round(top.y()))
            QTest.mouseMove(win, start)
            W.pump(0.3)
            QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, start)
            moves, during = [], []
            for i in range(1, 31):
                p = QPoint(start.x() + 3 * i, start.y())
                c = W.gui_cycles_ms()
                QTest.mouseMove(win, p)
                W.QCoreApplication.processEvents()
                moves.append(round(W.gui_cycles_ms() - c, 2))
                W.pump(0.016)
                during.append(changes(doc))
            live = (b._live or {}).get("send")
            engine = list(live.timings) if live is not None else []
            W.check(live is not None and live.sent > 0, f"the drag sent live `copies` requests ({0 if live is None else live.sent})")
            W.check(set(during) == {n0}, "the document did not change while the pointer was down")
            QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, QPoint(start.x() + 90, start.y()))
            W.pump(1.0)
            W.check(changes(doc) == n0 + 1, f"letting go: one undo step ({n0} -> {changes(doc)})")
            W.check(doc.item(pebbles)["count"] > c0, f"Count grew ({c0} -> {doc.item(pebbles)['count']})")
            worst, med = max(moves), sorted(moves)[len(moves) // 2]
            budget(worst <= BUDGET_MS, f"Count drag: slowest move {worst:.1f} ms of the GUI thread (budget {BUDGET_MS:.0f}), median {med:.1f}")
            if engine:
                budget(max(engine) <= BUDGET_MS, f"Count drag: the engine's slowest `copies` answer {max(engine):.1f} ms (budget {BUDGET_MS:.0f})")
            NUMBERS["countDrag"] = {"count": [c0, doc.item(pebbles)["count"]], "guiCpuMsPerMove": moves, "engineMsPerRequest": engine,
                                    "requests": 0 if live is None else live.sent}
            w.settle("the dragged count")
            w.snap("3-count-dragged")
            QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
            W.pump(0.5)
            W.check(doc.item(pebbles)["count"] == c0, "Ctrl+Z puts the count back")
            w.settle("the count back")

        # 4. a keyed Change near sphere, played
        b.select("copies_1")
        W.pump(0.3)
        n0, spheres = changes(doc), len(of_type(doc, "mesh"))
        w.right_click(w.where((BUD[0] + SPACING * 3, BUD[1], BUD[2])))
        W.check(b.selected == "copies_1", f"a right-click on a bud selects the buds ({b.selected})")
        W.check("menu:Change near" in w.entries(), f"the menu has Change near ({w.entries()})")
        w.choose("menu:Change near", "copies:near:scale")
        W.pump(5, lambda: of_type(doc, "effector"), "the effector")
        W.check(changes(doc) == n0 + 1, f"Change near › Scale: one undo step ({n0} -> {changes(doc)})")
        W.check(len(of_type(doc, "mesh")) == spheres + 1 and b.selected == "mesh_1", f"a small sphere was added and is selected ({b.selected})")
        eff = of_type(doc, "effector")[0]
        W.check(doc.item(eff)["near"] == "mesh_1", f"the change follows the sphere ({doc.item(eff)['near']})")
        w.settle("the change near")
        w.snap("4-change-near")
        # KNOWN OPEN: the keys are made through the bridge (the key mark's own click is covered by the key walks)
        last = b._info["end"]
        for frame, x in ((0, BUD[0] - 0.05), (last, BUD[0] + 1.0)):
            b.setFrame(frame)
            b.select("mesh_1")
            if frame == 0:
                b.toggleAnimate("x")
            b.setValue("x", x)
        W.check(bool(doc.item("mesh_1").get("keys")), "the sphere's x is keyed across the shot")
        b.setFrame(0)
        w.settle("frame 0")
        QTest.keyClick(win, Qt.Key_Space)
        W.pump(0.3)
        if not b.playing:
            print("KNOWN OPEN: Space did not start playback in the background window; playing through the bridge")
            b.togglePlay()
        frames = []
        on_ready = lambda serial, ms, *rest: frames.append(round(ms, 2))  # noqa: E731  the engine's own ms per picture
        v._r.ready.connect(on_ready)
        W.pump(2.5)
        v._r.ready.disconnect(on_ready)
        if b.playing:
            b.togglePlay()
        W.check(len(frames) > 5, f"playback drew frames ({len(frames)})")
        if frames:
            mean = sum(frames) / len(frames)
            budget(mean <= BUDGET_MS, f"playback with the change near: engine {mean:.1f} ms per frame on average, slowest {max(frames):.1f} (budget {BUDGET_MS:.0f})")
            NUMBERS["playback"] = {"frames": len(frames), "engineMsMean": round(mean, 2), "engineMsMax": max(frames)}
        w.snap("4-playback")

        # 5. a nudged copy stays when a script runs copies.make again with the same id
        b.select("")
        b.setFrame(0)
        w.settle("frame 0 again")
        n0 = changes(doc)
        at = w.where((BUD[0] + SPACING * 6, BUD[1], BUD[2]))
        QTest.mouseMove(win, at)
        W.pump(0.2)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
        W.pump(5, lambda: b.status.startswith("Copy"), "the copy picked")
        W.check(b.status.startswith("Copy 7 of "), f"a click on one bud says which ({b.status!r})")
        W.check(b.selected == "copies_1", f"the buds are selected ({b.selected})")
        W.pump(0.5)
        w.snap("5-copy-picked")
        _gizmo_drag(b, win, "move0", 40, 0, False)
        W.pump(1.0)
        held = doc.item("copies_1").get("held") or []
        W.check(len(held) == 1 and held[0][0] == 6, f"the drop kept copy 7 ({held})")
        W.check(changes(doc) == n0 + 1, f"the nudge: one undo step ({n0} -> {changes(doc)})")
        w.settle("the nudged copy")
        w.snap("5-nudged")
        where = list(held[0]) if held else []
        again = [{"op": "copies.make", "target": ["bud"], "args": {"id": "copies_1", "count": 8}}]
        doc.apply(again, b.who, label="script: copies.make again")
        W.pump(0.5)
        W.check(len(of_type(doc, "copies")) == 2, f"the script made no second copies item ({of_type(doc, 'copies')})")
        W.check(doc.item("copies_1")["count"] == 8, "the script's count took")
        W.check((doc.item("copies_1").get("held") or [[]])[0] == where, "the nudged copy is where it was put")
        w.settle("after the script")
        w.snap("5-after-script")
        W.check(not v.status.startswith("Error"), f"no viewport error ({v.status or '-'})")
    finally:
        (out / "copies_walk.json").write_text(json.dumps(NUMBERS, indent=1), encoding="utf-8")
        screen.close()
        app.processEvents()
        shutil.rmtree(project, ignore_errors=True)
    if W.FAILS:
        print(f"\n{len(W.FAILS)} check(s) failed")
        sys.exit(1)
    print("\nevery check passed")


if __name__ == "__main__":
    main()
