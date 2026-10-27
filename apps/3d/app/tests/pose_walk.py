# Pose walk (CL5): the Pose tool tried by real input in the real window (behind the person's work, never focused), the
# five-minute wave of 3d-simplicity SPEC § 1 (row 5:00) and § 4. A scratch project with a ground, two lights and the
# shot camera (2 s); Q, then real drags draw a body, an arm (Mirror makes the other) and two feet (clay_draw_walk's
# outlines). Then, by real keys and mouse only (bridge calls only read state to check it):
#   1. Shift+P: Pose on; the joints are found (one undo step), the bones drawn (lines, a dot per joint), the gizmo gone.
#   2. A click on each foot: a hold each (one undo step each), two orange rings.
#   3. The right arm's tip (the last bone of its chain: hand.R, else forearm.R) dragged up: the chip names the part
#      during the drag ("forearm.R · 64°"), the bones it turns light up; the release is ONE undo step that keys the
#      Turn of the arm's bones at the playhead and none of the held feet's. Timed: the screen's thread per move (the
#      move handler) and per solver result it applies, and the solver's parts (ik, pose, overlay) and the clay_pose
#      round trip (pose_solver.py; `timing` in the json).
#   4. Esc mid-drag (the left arm's tip): nothing in history, the keys exactly as before, the pointer back to the arrow.
#   5. Sculpting while posed: Q (Pose goes), the Add tile clicked, a real stroke along the RAISED right forearm, its
#      picture; then Shift+P again (the shape changed: the joints are found again, bends kept). The stroke's dabs (its
#      step's dabs file, clay space) must lie by the forearm AT REST, not where the posed arm was; with Mirror on, their
#      mirror by the left forearm at rest. The picture after "back to rest" (below) shows it.
#   5b. A right click on the clay: the menu (Pose: back to rest …), its picture; "Pose: back to rest" clicked: every
#      Turn key gone (Build page), one undo step, its picture.
#   6. Animate page (Alt+2): Home, a drag; End, a drag: the moved bones get keys at both times (two undo steps).
#   7. Names: Humanoid clicked in the settings panel: the joints show Humanoid names (one undo step), its picture.
#   8. A left drag on empty space turns the view (nothing in history).
# Pictures after each step and the numbers (pose_walk.json) go to the out folder. Not collected by pytest (needs the
# core built with CL5's clay skin and a GPU slot); the lead runs it:
#   heavy.ps1 run "sam: pose walk" gpu <venv python> apps\3d\app\tests\pose_walk.py --out <folder>
# Exit 0 = every check passed; else the failed checks are printed and it exits 1.
import argparse
import json
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import clay_walk as W  # noqa: E402  (puts this checkout's code first; its real-input helpers)
import clay_draw_walk as D  # noqa: E402  (the outlines and one timed real outline drag)

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum_core.keys import keys_of  # noqa: E402
from rostrum3d import KIND, clay_dabs, skin  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402

SCENE = D.SCENE.replace("end=2", "end=48")
BUDGET_MS = 33.0                 # the screen's thread per move and per result applied (two frames at 60 Hz)


def changes(doc):
    return len(doc.history.changes)


def turn_keys(clay: dict) -> dict:
    """{bone id: [(prop, t, v) …]} of every Turn key on the clay's bones."""
    return {b["id"]: sorted((k, round(x["t"], 4), round(x["v"], 4)) for k in skin.TURN for x in keys_of(b, k))
            for b, _ in skin.bones_of(clay)}


class Walk:
    def __init__(self, screen, out):
        self.s, self.out = screen, out
        self.win, self.b, self.v = screen.win, screen.bridge, screen.bridge.viewport
        self.p = self.v.pose
        self.vp = W.find(self.win.contentItem(), "viewport3d")

    def at(self, part):
        """A viewport point (parts 0..1) as window px."""
        top = self.vp.mapToScene(QPointF(0, 0))
        return QPoint(round(top.x() + part[0] * self.vp.width()), round(top.y() + part[1] * self.vp.height()))

    def bone(self, joint):
        """The drawn line of the bone that is the part `joint` ("hand.R")."""
        return next((ln for ln in self.p.lines if ln["joint"] == joint), None)

    def joints(self, ids) -> set:
        part = {ln["id"]: ln["joint"] for ln in self.p.lines}
        return {part.get(i, i) for i in ids}

    def tip(self, side, along=0.7):
        """A point on the last bone of the arm chain on `side` ("R"): hand, else forearm, else arm (an arm drawn with
        no hand blob ends at its forearm, rightly)."""
        part = next((f"{p}.{side}" for p in ("hand", "forearm", "arm") if self.bone(f"{p}.{side}")), "")
        W.check(bool(part), f"the {side} arm is drawn ({[x['joint'] for x in self.p.lines]})")
        return self.on_bone(part, along) if part else None

    def on_bone(self, joint, along=0.6):
        ln = self.bone(joint)
        W.check(ln is not None, f"{joint} is drawn ({[x['joint'] for x in self.p.lines]})")
        if ln is None:
            return None
        return self.at([ln["a"][0] + along * (ln["b"][0] - ln["a"][0]), ln["a"][1] + along * (ln["b"][1] - ln["a"][1])])

    def snap(self, name):
        W.pump(30, lambda: D.settled(self.v), f"{name}: the picture")
        W.pump(0.15)
        self.win.grabWindow().save(str(self.out / f"pose-{name}.png"))

    def click(self, pt, what):
        n0 = changes(self.b.doc)
        QTest.mouseMove(self.win, pt + QPoint(-3, 0))
        QTest.mouseMove(self.win, pt)
        W.pump(0.25)
        QTest.mouseClick(self.win, Qt.LeftButton, Qt.NoModifier, pt)
        W.pump(10, lambda: changes(self.b.doc) > n0 or self.v.status.startswith("Error"), f"{what}: the change")
        W.check(changes(self.b.doc) == n0 + 1, f"{what}: one undo step ({n0} -> {changes(self.b.doc)})")

    def drag(self, start, dy, what, esc=False, steps=24):
        """A real drag from `start` up by dy window px (the pointer rests first: the hover lights the part)."""
        doc, n0, clay = self.b.doc, changes(self.b.doc), self.b.selected
        before = turn_keys(doc.item(clay))
        QTest.mouseMove(self.win, start + QPoint(-3, 0))
        QTest.mouseMove(self.win, start)
        W.pump(0.4)
        lit = [ln["id"] for ln in self.p.lines if ln["lit"]]
        QTest.mousePress(self.win, Qt.LeftButton, Qt.NoModifier, start)
        W.pump(0.2)                                  # the press's pick
        ms, chip = [], ""
        for i in range(1, steps + 1):
            pt = start + QPoint(round(0.25 * dy * i / steps), round(-dy * i / steps))
            c0 = W.gui_cycles_ms()
            QTest.mouseMove(self.win, pt)
            ms.append(W.gui_cycles_ms() - c0)
            W.pump(0.016)
            chip = self.p.chip or chip
        if esc:
            QTest.keyClick(self.win, Qt.Key_Escape)
            W.pump(0.3)
            QTest.mouseRelease(self.win, Qt.LeftButton, Qt.NoModifier, pt)
            W.pump(1.0)
            W.check(changes(doc) == n0, f"{what}: Esc leaves nothing in history ({n0} -> {changes(doc)})")
            W.check(turn_keys(doc.item(clay)) == before, f"{what}: Esc puts every key back")
            W.check(self.p.cursor == "pick" and not self.p.dragging, f"{what}: the pointer is the arrow again")
        else:
            QTest.mouseRelease(self.win, Qt.LeftButton, Qt.NoModifier, pt)
            W.pump(10, lambda: changes(doc) > n0 or self.v.status.startswith("Error"), f"{what}: the change")
            W.check(changes(doc) == n0 + 1, f"{what}: one undo step ({n0} -> {changes(doc)})")
            W.check(chip != "" and "°" in chip, f"{what}: the chip names the part and its bend ({chip!r})")
        W.check(not self.v.status.startswith("Error"), f"{what}: no error ({self.v.status or '-'})")
        slow = sorted(ms)[len(ms) * 9 // 10] if ms else 0
        return {"what": what, "lit": lit, "chip": chip, "moveMsP90": round(slow, 2), "moveMsMax": round(max(ms or [0]), 2),
                "moves": len(ms), "timing": timing(self.v.pose_tool.timings), "keys": turn_keys(doc.item(clay)),
                "before": before}

    def find_text(self, text, root=None):
        """The visible item whose `text` is `text` (a menu entry, a choice), anywhere in the window (popups too)."""
        root = root or self.win.contentItem().parentItem() or self.win.contentItem()
        if root.isVisible() and root.property("text") == text:
            return root
        for c in root.childItems():
            hit = self.find_text(text, c)
            if hit is not None:
                return hit
        return None

    def click_text(self, text, what):
        item = self.find_text(text)
        W.check(item is not None, f"{what}: '{text}' is there")
        if item is not None:
            W.click(self.win, item)
        return item is not None


def timing(rows: list[dict]) -> dict:
    """p50 / p90 / max of each part over a drag's solver results (ms), and how many results there were."""
    out = {"results": len(rows)}
    for k in sorted({k for r in rows for k in r}):
        xs = sorted(r[k] for r in rows if k in r)
        out[k] = {"p50": xs[len(xs) // 2], "p90": xs[len(xs) * 9 // 10], "max": xs[-1]}
    return out


def moved(rec) -> set:
    return {b for b, ks in rec["keys"].items() if ks != rec["before"].get(b)}


def wave(w: Walk, clay: str, report: dict):
    doc = w.b.doc
    n0 = changes(doc)
    QTest.keyClick(w.win, Qt.Key_P, Qt.ShiftModifier)
    W.pump(30, lambda: doc.item(clay).get("bones") or w.v.status.startswith("Error"), "the joints")
    W.pump(0.5)
    W.check(w.p.on, "Shift+P turns Pose on")
    W.check(changes(doc) == n0 + 1, f"finding the joints is one undo step ({n0} -> {changes(doc)})")
    W.check(len(w.p.lines) >= 7 and len(w.p.dots) == len(w.p.lines), f"bones drawn ({len(w.p.lines)} lines)")
    W.check(not w.v.gizmo.handles, "no gizmo while Pose is on")
    report["joints"] = [ln["joint"] for ln in w.p.lines]
    w.snap("1-joints")
    for foot in ("foot.L", "foot.R"):
        pt = w.on_bone(foot, 0.5)
        if pt is not None:
            w.click(pt, f"hold {foot}")
    W.check(len(w.p.rings) == 2, f"two orange hold rings ({len(w.p.rings)})")
    w.snap("2-holds")
    hand = w.tip("R")
    if hand is None:
        return
    rec = w.drag(hand, 0.25 * w.vp.height(), "wave: the right arm's tip up")
    report["wave"] = {k: v for k, v in rec.items() if k not in ("keys", "before")}
    turned = w.joints(moved(rec))
    W.check(bool(turned & {"arm.R", "forearm.R"}), f"the right arm bends ({sorted(turned)})")
    W.check(not turned & {"foot.L", "foot.R", "leg.L", "leg.R", "shin.L", "shin.R"}, "the held feet are not keyed")
    W.check(rec["moveMsP90"] <= BUDGET_MS, f"a move on the screen's thread: p90 {rec['moveMsP90']} ms (≤ {BUDGET_MS})")
    apply = rec["timing"].get("applyMs", {}).get("p90", 0)
    W.check(apply <= BUDGET_MS, f"a solver result applied on the screen's thread: p90 {apply} ms (≤ {BUDGET_MS})")
    W.check(0 < rec["timing"]["results"] <= rec["moves"], f"moves coalesced: {rec['timing']['results']} results "
            f"for {rec['moves']} moves")
    w.snap("3-wave")
    left = w.tip("L")
    if left is not None:
        report["esc"] = {k: v for k, v in w.drag(left, 0.2 * w.vp.height(), "Esc mid-drag", esc=True).items()
                         if k not in ("keys", "before")}
        w.snap("4-esc")
    sculpt_posed(w, clay, report)
    menu_rest(w, clay, report)


def _seg_dist(p, a, b) -> float:
    ab = [y - x for x, y in zip(a, b)]
    t = max(0.0, min(1.0, sum((q - x) * d for q, x, d in zip(p, a, ab)) / (sum(d * d for d in ab) or 1e-12)))
    return math.dist(p, [x + t * d for x, d in zip(a, ab)])


def segments(clay: dict, t) -> dict:
    """{joint: (head, tail, length)} in the clay's own space, at rest (t None) or posed at t."""
    chain = skin.bones_of(clay)
    return {b.get("joint", b["id"]): (s[:3], s[3:], float(b.get("length", 0.0)))
            for m, (b, _) in zip(skin.transforms(chain, t), chain) for s in [skin.segment(m, b)]}


def sculpt_posed(w: Walk, clay: str, report: dict):
    """An Add stroke along the raised right forearm, then its dabs checked against the forearm at rest."""
    doc, v = w.b.doc, w.v
    part = next((p for p in ("forearm.R", "arm.R") if w.bone(p)), "")
    ln = w.bone(part) if part else None
    W.check(ln is not None, f"sculpt: the raised right arm is drawn ({part})")
    if ln is None:
        return
    a, b = w.at(ln["a"]), w.at(ln["b"])                 # the posed forearm on screen, before Pose goes
    posed, rest = segments(doc.item(clay), w.b.time), segments(doc.item(clay), None)
    QTest.keyClick(w.win, Qt.Key_Q)
    W.pump(0.5)
    W.check(v.clay.on and not w.p.on, f"Q: Clay on, Pose off ({v.clay.on}, {w.p.on})")
    W.pick_tile(w.win, v.clay, "Add", "add")
    n_steps = len(doc.item(clay)["steps"])
    pts = [QPoint(round(a.x() + (b.x() - a.x()) * k), round(a.y() + (b.y() - a.y()) * k))
           for k in [0.2 + 0.6 * i / 20 for i in range(21)]]
    QTest.mouseMove(w.win, pts[0])
    W.pump(0.4)
    QTest.mousePress(w.win, Qt.LeftButton, Qt.NoModifier, pts[0])
    W.pump(5, lambda: not v.clay._busy and v.clay._phase in ("sculpt", "orbit", ""), "the stroke's begin")
    W.check(v.clay._phase == "sculpt", f"sculpt: the press on the raised forearm began a stroke ({v.clay._phase!r})")
    for p in pts[1:]:
        QTest.mouseMove(w.win, p)
        W.pump(0.03)
    QTest.mouseRelease(w.win, Qt.LeftButton, Qt.NoModifier, pts[-1])
    W.pump(10, lambda: not v.clay._ending and len(doc.item(clay)["steps"]) > n_steps, "the stroke's step")
    W.check(not v.status.startswith("Error"), f"sculpt: no error ({v.status or '-'})")
    w.snap("5-sculpt-posed")
    it = doc.item(clay)
    step = it["steps"][-1] if len(it["steps"]) > n_steps else {}
    rows = clay_dabs.read(doc.folder, step["dabs"]) if step.get("dabs") else step.get("dabList") or []
    W.check(bool(rows), f"sculpt: the stroke's dabs are there ({len(rows)})")
    out = {"part": part, "dabs": len(rows)}
    if rows and part in rest:
        h, t_, length = rest[part]
        ph, pt_, _ = posed[part]
        pts3 = [r[:3] for r in rows if (r[0] >= 0) == ((h[0] + t_[0]) >= 0)]       # this side's dabs
        med = lambda xs: sorted(xs)[len(xs) // 2] if xs else math.inf  # noqa: E731
        d_rest = med([_seg_dist(p, h, t_) for p in pts3])
        d_posed = med([_seg_dist(p, ph, pt_) for p in pts3])
        out.update(restM=round(d_rest, 4), posedM=round(d_posed, 4), boneM=round(length, 4))
        W.check(d_rest <= 0.5 * length and d_rest < 0.5 * d_posed,
                f"sculpt: the dabs sit by {part} at rest (median {d_rest:.3f} m; posed arm {d_posed:.3f} m; bone {length:.3f} m)")
        other = part[:-1] + "L"
        if it.get("symmetry", "x") != "off" and other in rest:
            lh, lt, _ = rest[other]
            d_mirror = med([_seg_dist([-p[0], p[1], p[2]], lh, lt) for p in pts3])
            out["mirrorM"] = round(d_mirror, 4)
            W.check(d_mirror <= 0.5 * length, f"sculpt: Mirror: their mirror sits by {other} at rest ({d_mirror:.3f} m)")
    report["sculptPosed"] = out
    n0 = changes(doc)                                 # Pose again: the shape changed, so the joints are found again
    QTest.keyClick(w.win, Qt.Key_P, Qt.ShiftModifier)
    W.pump(10, lambda: w.p.on and (changes(doc) > n0 or not _stale(w, clay)), "Pose again")
    W.pump(1.0)
    W.check(w.p.on and len(w.p.lines) >= 7, f"Shift+P: Pose back on, bones drawn ({len(w.p.lines)})")


def _stale(w: Walk, clay: str) -> bool:
    from screen3d import pose_link
    return pose_link.out_of_date(w.b.doc.item(clay), w.b.doc.data)


def menu_rest(w: Walk, clay: str, report: dict):
    """A right click on the clay: the menu; Pose: back to rest (Build page: every Turn key gone, one undo step)."""
    doc = w.b.doc
    body = w.on_bone("body", 0.5)
    if body is None:
        return
    QTest.mouseMove(w.win, body)
    W.pump(0.2)
    QTest.mouseClick(w.win, Qt.RightButton, Qt.NoModifier, body)
    W.pump(5, lambda: w.find_text("Pose: back to rest") is not None, "the right-click menu")
    w.snap("7-menu")
    n0 = changes(doc)
    if w.click_text("Pose: back to rest", "the menu"):
        W.pump(10, lambda: changes(doc) > n0, "back to rest: the change")
        W.check(changes(doc) == n0 + 1, f"back to rest: one undo step ({n0} -> {changes(doc)})")
        left = {b: ks for b, ks in turn_keys(doc.item(clay)).items() if ks}
        W.check(not left, f"back to rest (Build page): no Turn key left ({sorted(left)})")
        w.snap("8-rest")
    report["rest"] = {"keysLeft": sum(len(ks) for ks in turn_keys(doc.item(clay)).values())}


def humanoid(w: Walk, report: dict):
    """Names: Humanoid clicked in the settings panel."""
    doc, n0 = w.b.doc, changes(w.b.doc)
    names = W.find(w.win.contentItem(), "poseNames")
    W.check(names is not None, "the Names row is in the settings panel")
    item = w.find_text("Humanoid", names) if names is not None else None
    W.check(item is not None, "its Humanoid choice is there")
    if item is None:
        return
    W.click(w.win, item)
    W.pump(10, lambda: changes(doc) > n0, "Humanoid: the change")
    W.pump(0.5)
    shown = sorted(d["joint"] for d in w.p.dots)
    W.check(changes(doc) == n0 + 1 and w.p.names == "humanoid", f"Humanoid names: one undo step ({w.p.names})")
    W.check(any(n in shown for n in ("Hips", "RightUpperArm", "LeftUpperArm")), f"the joints say Humanoid names ({shown})")
    report["humanoid"] = shown
    w.snap("9-humanoid")


def empty_drag(w: Walk, report: dict):
    """SPEC § 1: in Pose a left drag on empty space turns the view; nothing changes in the document."""
    doc, n0 = w.b.doc, changes(w.b.doc)
    cam0 = dict(w.v.cam.request(w.b.frame, 640, 360))
    start = w.at([0.08, 0.12])
    QTest.mouseMove(w.win, start)
    W.pump(0.3)
    QTest.mousePress(w.win, Qt.LeftButton, Qt.NoModifier, start)
    W.pump(0.3)                                    # the press's pick: nothing there
    shape = ""
    for i in range(1, 16):
        QTest.mouseMove(w.win, start + QPoint(6 * i, 2 * i))
        W.pump(0.016)
        shape = w.p.cursor if i == 8 else shape
    QTest.mouseRelease(w.win, Qt.LeftButton, Qt.NoModifier, start + QPoint(90, 30))
    W.pump(1.0)
    cam1 = dict(w.v.cam.request(w.b.frame, 640, 360))
    W.check(cam1 != cam0, f"a left drag on empty space turns the view ({w.v.mode})")
    W.check(shape == "rotate", f"the turn pointer while it turns ({shape!r})")
    W.check(changes(doc) == n0 and w.p.on, "turning the view changes nothing, Pose stays on")
    report["emptyDrag"] = {"mode": w.v.mode, "pointer": shape}
    w.snap("10-view-turned")


def animate(w: Walk, report: dict):
    QTest.keyClick(w.win, Qt.Key_2, Qt.AltModifier)
    W.pump(1.0)
    W.check(w.b.page == "animate" and w.p.on, f"Animate page, Pose still on ({w.b.page})")
    times = []
    for key, dy, name in ((Qt.Key_Home, 0.15, "5-animate-start"), (Qt.Key_End, -0.12, "6-animate-end")):
        QTest.keyClick(w.win, key)
        W.pump(1.0)
        hand = w.tip("R")
        if hand is None:
            return
        times.append(round(w.b.time, 4))
        rec = w.drag(hand, dy * w.vp.height(), f"animate: a drag at {w.b.time:.2f} s")
        w.snap(name)
    ts = {t for ks in rec["keys"].values() for _, t, _ in ks}
    W.check(all(t in ts for t in times), f"keys at both times {times} ({sorted(ts)})")
    report["animate"] = {"times": times, "keyTimes": sorted(ts)}


def main():
    ap = argparse.ArgumentParser(description="The Pose tool by real input in the real window")
    ap.add_argument("--out", default=r"C:\Users\Sam\.rostrum\waves\results\3d-cl5\sam")
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)
    W.OUT = out
    project = Path(tempfile.mkdtemp(prefix="rostrum-pose-"))
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("scene.py", run_source(SCENE, "scene.py"))
    doc.save()
    screen = W.app3d.Screen(W.SIZE)
    report = {}
    try:
        screen.show(doc, autosave=True)
        win, v = screen.win, screen.bridge.viewport
        W.pump(60, screen.ready, "the first picture")
        vp_item = W.find(win.contentItem(), "viewport3d")
        QTest.keyClick(win, Qt.Key_Q)
        W.pump(0.3)
        top = vp_item.mapToScene(QPointF(0, 0))
        w_, h = vp_item.width(), vp_item.height()
        cx, cy, rx, ry = top.x() + 0.5 * w_, top.y() + 0.55 * h, 0.1 * h, 0.2 * h
        body = D.draw(screen, win, "Body", D.pear(cx, cy, rx, ry), out, rest=0.1)
        clay = body["newClays"][0] if body["newClays"] else ""
        W.check(bool(clay), "the body is a new clay")
        if clay:
            sx, sy = cx + 0.5 * rx, cy - 0.45 * ry               # an arm from the right shoulder, out and down
            D.draw(screen, win, "Arm", [QPoint(round(sx), round(sy))] +
                   D.loop((sx + 0.12 * h, sy + 0.04 * h), 0.13 * h, 0.022 * h, start=math.pi, tilt=0.35), out)
            for side, name in ((-1, "Left foot"), (1, "Right foot")):
                fx, fy = cx + side * 0.3 * rx, cy + 0.85 * ry
                D.draw(screen, win, name, [QPoint(round(fx), round(fy))] +
                       D.loop((cx + side * 0.45 * rx, cy + ry + 0.01 * h), 0.05 * h, 0.022 * h, start=-math.pi / 2), out)
            QTest.keyClick(win, Qt.Key_V)               # back to Select, the clay still selected
            W.pump(0.3)
            walk = Walk(screen, out)
            t0 = time.perf_counter()
            wave(walk, clay, report)
            animate(walk, report)
            humanoid(walk, report)
            empty_drag(walk, report)
            report["walkS"] = round(time.perf_counter() - t0, 1)
    except Exception as e:  # noqa: BLE001  a crash is a failed walk, said with its reason
        W.FAILS.append(f"the walk stopped: {type(e).__name__}: {e}")
    finally:
        report["fails"] = W.FAILS
        (out / "pose_walk.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
        screen.close()
        W.pump(1.0)
        shutil.rmtree(project, ignore_errors=True)
    print(f"{len(W.FAILS)} failed check(s); numbers and pictures in {out}")
    for f in W.FAILS:
        print("  " + f)
    app.quit()
    return 1 if W.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
