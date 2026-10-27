# CL7 walk: SPEC § 1 "The first 5 minutes" (3d-simplicity) from a New project to the rendered picture, by a scripted
# hand with real input (QTest mouse and keys on the visible controls, found by objectName; the bridge is only READ, for
# the checks) in the real 3D window at 1646 x 900, behind the person's work, never focused. The hand is paced like a
# quick person (glides of ~0.5-1 s, small pauses) so the recording is watchable. The steps (SPEC § 1's table):
#   1. Clay in the rail (Draw a shape chosen)            7. body Base colour orange (the colour square); eye Material ▾
#   2. a pear body drawn over the ground                    Glossy + black
#   3. an arm from the body's side (joins, mirrored)     8. Pose: both feet held, the right hand dragged up
#   4. a foot (one oval; Mirror makes the other)         9. Lights › Soft light, a click on the cheek
#   5. Smooth over the shoulders, Add a brow, Carve a   10. a right-drag to a side-above view, Make this the shot
#      mouth (the panel's brush buttons)                11. Render (the blue button) until the picture shows
#   6. Shapes › Sphere, one click on the face: an eye and its mirrored copy
# Each step: its time from its first input until the app showed its result (SPEC slot = budget), the app's own waits
# inside it, every release timed (an outline's puff, each brush stroke, the pose drag), discrete clicks that show nothing
# for > 0.2 s flagged, and its checks read from the document. Where SPEC § 1 can't be followed as written, the walk works
# around it (only to continue) and records a STUMBLE. One picture per step (the window's own pixels) and cl7_walk.json
# go to the out folder; the walk is recorded (grabWindow ~15 fps, the hand's pointer and the step drawn on) into
# cl7-five-minutes.mp4 and cl7-five-minutes-share.mp4 (~8 Mbit/s). The lead runs it:
#   heavy.ps1 run "sam: cl7 walk" gpu <venv python> apps\3d\tools\cl7_walk.py <out folder>
# Exit 0 = every check passed and every step was within its budget; else they are printed and it exits 1.
import json
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-cl7\walk")
SCRATCH = Path(os.environ.get("CL7_SCRATCH", r"C:\Users\Sam\.rostrum\waves\scratch\sam-cl7-memberA"))
RECORD = os.environ.get("CL7_RECORD", "1") != "0"
UNTIL = int(os.environ.get("CL7_UNTIL", "11"))              # stop after this step (short tries while developing)
sys.argv = sys.argv[:1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_draw_walk as D  # noqa: E402  (its helpers; puts this checkout's code first)
import clay_walk as W  # noqa: E402
from cl7_record import Clock, Hand, Recorder  # noqa: E402

from PySide6.QtCore import QPointF, Qt  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d import files_3d  # noqa: E402

BUDGET = [("Clay", 10), ("Body", 30), ("Arm", 60), ("Feet", 30), ("Smooth, brow, mouth", 90), ("Eye", 30),
          ("Colour", 50), ("Wave", 40), ("Light", 20), ("Angle", 30), ("Render", 30)]
EYE = (0.3, -0.42)                                         # where the left eye goes, in the body's half-axes
EYE_AGAIN = (0.52, -0.42)                                  # (the workaround's second click, farther out)


def items_of(doc, kind):
    out, stack = [], list(doc.data.get("items", []))
    while stack:
        it = stack.pop()
        out += [it] if it.get("type") == kind else []
        stack += it.get("children", [])
    return out


def all_items(item):
    yield item
    for c in item.childItems():
        yield from all_items(c)


def visible(item):
    while item is not None:
        if not item.isVisible():
            return False
        item = item.parentItem()
    return True


def named(root, prefix=""):
    """Every visible named item (objectName starting with `prefix`): {name: (x, y, w, h)} in window px."""
    out = {}
    for c in all_items(root):
        n = c.objectName()
        if n and n.startswith(prefix) and c.isVisible() and c.width() > 0:
            p = c.mapToScene(QPointF(0, 0))
            out[n] = [round(p.x()), round(p.y()), round(c.width()), round(c.height())]
    return out


def by_text(root, text, within=None):
    """The visible item whose `text` is exactly `text` (buttons without an objectName), inside `within` (a rect) if given."""
    for c in all_items(root):
        if c.property("text") == text and visible(c) and c.width() > 0:
            p = c.mapToScene(QPointF(c.width() / 2, c.height() / 2))
            if within is None or (within[0] <= p.x() <= within[0] + within[2] and within[1] <= p.y() <= within[1] + within[3]):
                return c
    return None


def child_named(item, name):
    for c in all_items(item):
        if c.objectName() == name and visible(c):
            return c
    return None


def bones(clay):
    out, stack = {}, list(clay.get("bones", []))
    while stack:
        b = stack.pop()
        out[b.get("joint") or b["id"]] = b
        stack += b.get("bones", [])
    return out


def hue(hex_):
    r, g, b = (int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5))
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == mn:
        return None, 0.0, mx
    d = mx - mn
    h = ((g - b) / d) % 6 if mx == r else (b - r) / d + 2 if mx == g else (r - g) / d + 4
    return 60 * h, d / mx, mx


class Walk:
    def __init__(self, screen, report):
        self.screen, self.report = screen, report
        self.win, self.b, self.v = screen.win, screen.bridge, screen.bridge.viewport
        self.root = self.win.contentItem()
        self.clock = Clock(None)
        self.hand = Hand(self.win, self.clock)
        self.rec = None
        vp = W.find(self.root, "viewport3d")
        top = vp.mapToScene(QPointF(0, 0))
        self.vp = (top.x(), top.y(), vp.width(), vp.height())
        x, y, w, h = self.vp
        self.cx, self.cy, self.rx, self.ry = x + 0.5 * w, y + 0.6 * h, 0.2 * h, 0.25 * h
        self.h = h
        self.clay = ""

    # ---- small helpers ---------------------------------------------------------------------------------------------
    @property
    def doc(self):
        return self.b.doc

    def at(self, u, v):
        """A window point on the body, in its half-axes from its middle (u right, v down)."""
        return QPointF(self.cx + u * self.rx, self.cy + v * self.ry)

    def changes(self):
        return len(self.doc.history.changes)

    def settled(self):
        return D.settled(self.v)

    def control(self, name, why=""):
        """A visible control by objectName; a missing one fails the step's check (and its on-screen names are kept)."""
        item = W.find(self.root, name)
        if not self.clock.check(item is not None, f"the {name} control is on screen{(' (' + why + ')') if why else ''}"):
            self.clock.cur.setdefault("onScreen", named(self.root))
        return item

    def click(self, name, why="", secs=0.6):
        item = self.control(name, why)
        return None if item is None else self.hand.click_item(item, secs)

    def spheres(self, before):
        return [m for m in items_of(self.doc, "mesh") if m["id"] not in before and m.get("shape") == "sphere"]

    def steps_of(self):
        return len(self.doc.item(self.clay).get("steps", [])) if self.clay and self.doc.has(self.clay) else 0

    def picture(self, n, name):
        self.clock.wait(self.settled, "the picture to settle", 30)
        W.pump(0.2)
        slug = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
        path = OUT / f"{n:02d}-{slug}.png"
        self.win.grabWindow().save(str(path))
        return str(path)

    def outline(self, what, pts, secs):
        """A drawn outline, released: timed until its change and its picture (the puff)."""
        n0, before = self.changes(), {c["id"] for c in items_of(self.doc, "clay")}
        t = self.hand.drag(pts, secs, rest=0.35)
        self.clock.release(f"{what}: the puff (change)", t, lambda: self.changes() > n0 or self.v.status.startswith("Error"))
        self.clock.release(f"{what}: the puff (picture)", t, self.settled)
        self.clock.check(not self.v.status.startswith("Error"), f"{what}: no error ({self.v.status or '-'})")
        self.clock.check(self.changes() == n0 + 1, f"{what}: one undo step ({n0} -> {self.changes()})")
        return [c["id"] for c in items_of(self.doc, "clay") if c["id"] not in before]

    def brush(self, label, a, b, bend=0.0, secs=0.9):
        """A brush tile clicked, then one stroke from a to b (a little arc of `bend` x the length): timed release."""
        tool = self.v.clay
        tile = self.control(f"clayBrush{label}")
        if tile is None:
            return
        t = self.hand.click_item(tile)
        self.clock.feedback(f"{label} tile chosen", t, lambda: tool.tool == label.lower())
        n, s0 = 24, self.steps_of()
        dx, dy = b.x() - a.x(), b.y() - a.y()
        pts = [QPointF(a.x() + dx * i / n - dy * bend * math.sin(math.pi * i / n),
                       a.y() + dy * i / n + dx * bend * math.sin(math.pi * i / n)) for i in range(n + 1)]
        dabs = []
        t = self.hand.drag(pts, secs, rest=0.3, on_move=lambda i: dabs.append(round(time.perf_counter() * 1000)))
        self.clock.release(f"{label} stroke: its step", t, lambda: not tool._ending and self.steps_of() > s0)
        self.clock.release(f"{label} stroke: the picture", t, self.settled)
        steps = self.doc.item(self.clay).get("steps", [])
        self.clock.check(len(steps) == s0 + 1 and steps[-1].get("brush") == label.lower(),
                         f"{label}: one {label.lower()} step on the clay ({s0} -> {len(steps)}, "
                         f"{steps[-1].get('brush') if steps else '-'})")
        self.clock.check(steps[-1].get("symmetry", "x") == "x" if steps else False,
                         f"{label}: mirrored ({steps[-1].get('symmetry') if steps else '-'})")
        if tool.timings:
            worst = max(x.get("ms", x.get("engineMs", 0)) or 0 for x in tool.timings[-24:])
            self.clock.cur.setdefault("dabWorstMs", {})[label] = round(worst, 1)

    def swatch(self, row):
        """The colour square beside a row (row:<id>'s swatch), clicked: the picker opens."""
        r = W.find(self.root, row)
        sw = child_named(r, "swatch") if r is not None else None
        self.clock.check(sw is not None, f"the colour square beside {row} is on screen")
        if sw is None:
            self.clock.cur.setdefault("onScreen", named(self.root))
            return False
        t = self.hand.click_item(sw)
        return self.clock.feedback("the colour picker opens", t, lambda: W.find(self.root, "colourSquare") is not None) < 1e9

    def pick(self, h, s, v):
        """In the open picker: a click on the hue strip at hue `h` (0-1), then on the square at saturation s, value v."""
        strip, sq = W.find(self.root, "hueStrip"), W.find(self.root, "colourSquare")
        if strip is None or sq is None:
            return self.clock.check(False, "the picker's hue strip and colour square are on screen")
        if h is not None:
            p = strip.mapToScene(QPointF(7 + h * (strip.width() - 14), strip.height() / 2))
            self.hand.click(p, 0.5)
            W.pump(0.2)
        p = sq.mapToScene(QPointF(s * (sq.width() - 1), (1 - v) * (sq.height() - 1)))
        self.hand.click(p, 0.5)
        W.pump(0.3)
        self.hand.key(Qt.Key_Escape)                       # the picker closes; the change is kept
        W.pump(0.4)
        if W.find(self.root, "colourSquare") is not None:   # (Esc didn't reach it: click on empty panel space)
            self.clock.stumble("Esc does not close the colour picker", "shared/gui-kit SidePopup", 1)
            x, y, w, h_ = self.vp
            self.hand.click(QPointF(x + w + 40, y + h_ - 30), 0.4)
        return True

    def open_material(self, mat_id):
        """The rail's Materials ball, then the material's row: the settings panel shows the material (Base colour)."""
        if self.click("rail_materials", "the rail's Materials") is None or not mat_id:
            return
        row = self.control(f"matlist:{mat_id}", "the material in the Materials list")
        if row is not None:
            t = self.hand.click_item(row, 0.5)
            self.clock.feedback("the material's panel", t, lambda: W.find(self.root, "row:baseColor") is not None)

    def material(self, item_id):
        it = self.doc.item(item_id)
        mid = it.get("material") or ""
        return self.doc.item(mid) if mid and self.doc.has(mid) else {}

    # ---- the steps ---------------------------------------------------------------------------------------------
    def s1_clay(self):
        t = self.click("rail_clay", "the rail's Clay")
        if t:
            self.clock.feedback("Clay on", t, lambda: self.v.clay.on)
        self.clock.check(self.v.clay.on and self.v.clay.tool == "draw", f"Clay on, Draw a shape chosen ({self.v.clay.tool})")
        rail = named(self.root, "rail_")
        self.clock.cur["rail"] = sorted(rail)

    def s2_body(self):
        pts = [QPointF(p) for p in D.pear(self.cx, self.cy, self.rx, self.ry)]
        new = self.outline("Body", pts, 2.2)
        self.clock.check(len(new) == 1, f"a new clay ({new})")
        self.clay = new[0] if new else ""
        if not self.clay:
            raise RuntimeError("no body to go on with")
        c = self.doc.item(self.clay)
        self.clock.check(self.b.selected == self.clay, f"the body is selected ({self.b.selected})")
        sym = c.get("symmetry") or (c.get("steps") or [{}])[0].get("symmetry")
        self.clock.check(sym == "x", f"Mirror is on ({sym})")
        mat = self.material(self.clay)
        self.clock.check("clay" in str(mat.get("name", "")).lower() + str(mat.get("start", "")).lower(),
                         f"new clay starts as Clay ({mat.get('name')})")
        rail = named(self.root, "rail_")
        self.clock.check("rail_paint" in rail and "rail_pose" in rail, f"the rail shows Paint and Pose ({sorted(rail)})")

    def arm_pts(self, side=1):
        sx, sy = self.cx + side * 0.62 * self.rx, self.cy - 0.2 * self.ry
        arm = D.loop((sx + side * 0.09 * self.h, sy - 0.03 * self.h), 0.09 * self.h, 0.025 * self.h,
                     start=math.pi if side > 0 else 0, tilt=-0.3 * side)
        return [QPointF(sx, sy)] + [QPointF(p) for p in arm]

    def s3_arm(self):
        pts, s0 = self.arm_pts(), self.steps_of()
        self.hand.glide(pts[0], 0.7)
        self.clock.wait(lambda: self.v.clay.drawObj.joining == self.clay, "the body outlined under the pencil", 3)
        self.clock.check(self.v.clay.drawObj.joining == self.clay, "resting on the body outlines it (joining)")
        new = self.outline("Arm", pts, 1.6)
        self.clock.check(not new and self.steps_of() == s0 + 1, f"the arm joins the body: one step on it ({new})")
        st = (self.doc.item(self.clay).get("steps") or [{}])[-1]
        self.clock.check(st.get("symmetry", "x") == "x", f"the arm is mirrored ({st.get('symmetry')})")

    def foot_pts(self, side=1):
        fx, fy = self.cx + side * 0.3 * self.rx, self.cy + 0.85 * self.ry
        foot = D.loop((self.cx + side * 0.45 * self.rx, self.cy + self.ry + 0.01 * self.h), 0.05 * self.h, 0.022 * self.h,
                      start=-math.pi / 2)
        return [QPointF(fx, fy)] + [QPointF(p) for p in foot]

    def s4_feet(self):
        s0 = self.steps_of()
        new = self.outline("Foot", self.foot_pts(), 1.2)
        self.clock.check(not new and self.steps_of() == s0 + 1, f"the foot joins the body: one step ({new})")

    def s5_shape(self):
        self.brush("Smooth", self.at(0.3, -0.5), self.at(0.75, -0.12), bend=-0.15)
        self.brush("Add", self.at(0.12, -0.62), self.at(0.45, -0.62), bend=-0.12)
        self.brush("Carve", self.at(-0.22, -0.22), self.at(0.22, -0.22), bend=0.12)

    def s6_eye(self):
        self.click("rail_shapes", "the rail's Shapes")
        tile = self.control("fly_mesh:sphere", "Shapes › Sphere")
        if tile is None:
            return
        self.hand.click_item(tile, 0.4)
        before, n0 = {m["id"] for m in items_of(self.doc, "mesh")}, self.changes()
        t = self.hand.click(self.at(*EYE), 0.7)
        self.clock.feedback("the eye placed", t, lambda: self.changes() > n0 or self.v.status.startswith("Error"))
        self.clock.wait(self.settled, "the eye drawn")
        sp = [m for m in items_of(self.doc, "mesh") if m["id"] not in before and m.get("shape") == "sphere"]
        self.clock.cur["firstEye"] = [{k: m.get(k) for k in ("id", "name", "radius", "x", "y", "z", "mirror")} for m in sp]
        body = self.doc.item(self.clay)
        if len(sp) == 1:
            self.clock.stumble(f"one click on the face where an eye goes made ONE sphere, no mirrored copy (radius "
                               f"{sp[0].get('radius')} m, x {sp[0].get('x'):.3f} m from the middle; the body's x "
                               f"{body.get('x', 0):.3f}); undone and clicked again farther out",
                               "apps/3d/python/rostrum3d/surface_place.py:54 mirrors (ON_THE_MIRROR x the part's size) "
                               "with apps/3d/app/screen3d/placing.py:20 size_class (a fifth of the whole clay)", 3)
            self.click("undoButton", "the header's undo")
            self.clock.wait(lambda: not self.doc.has(sp[0]["id"]), "the undo", 5)
            self.click("rail_shapes", "the rail's Shapes")
            tile = self.control("fly_mesh:sphere", "Shapes › Sphere")
            if tile is None:
                return
            self.hand.click_item(tile, 0.4)
            t = self.hand.click(self.at(*EYE_AGAIN), 0.5)
            self.clock.feedback("the eye placed (again)", t, lambda: self.spheres(before) or self.v.status.startswith("Error"))
            self.clock.wait(self.settled, "the eye drawn")
            sp = self.spheres(before)
            self.clock.cur["secondEye"] = [{k: m.get(k) for k in ("id", "name", "radius", "x", "y", "z", "mirror")} for m in sp]
        r = next((m.get("radius", 0) for m in sp if not m.get("mirror")), 0)      # (a copy keeps only its link)
        self.clock.cur["eyeRadius"] = r
        if sp and r > 0.025:
            self.clock.stumble(f"the eye is not 'sized for the face': radius {r} m, a fifth of the whole clay",
                               "apps/3d/app/screen3d/placing.py:20 size_class", 2)
        mir = [m for m in sp if m.get("mirror")]
        self.clock.check(len(sp) == 2, f"two spheres: the eye and its mirrored copy ({len(sp)})")
        self.clock.check(len(mir) == 1 and any(m["id"] == mir[0]["mirror"] for m in sp), "the copy mirrors the other")
        self.eyes = [m["id"] for m in sp]
        self.eye_at = EYE_AGAIN if len(self.clock.cur["firstEye"]) == 1 else EYE
        self.eye = next((m["id"] for m in sp if not m.get("mirror")), sp[0]["id"] if sp else "")

    def s7_colour(self):
        # the body: a click on it (the eye was selected by its placing), then Base colour's square, an orange
        t = self.hand.click(self.at(0.0, 0.35), 0.7)
        self.clock.feedback("the body selected", t, lambda: self.b.selected == self.clay)
        self.clock.check(self.b.selected == self.clay, f"a click on the body selects it ({self.b.selected})")
        W.pump(0.3)
        if W.find(self.root, "row:baseColor") is None:
            self.clock.stumble("with the clay selected the panel shows only 'Material: Clay ▾', no Base colour square; "
                               "went through the rail's Materials list › Clay (the material's own panel)",
                               "apps/3d/app/screen3d/bridge_rows.py:49 (a clay is not in materials.USERS, so no "
                               "MaterialRow / colour row for its material)", 2)
            self.open_material(self.material(self.clay).get("id", ""))
        if self.swatch("row:baseColor"):
            self.pick(25 / 360, 0.85, 0.9)
        mat = self.material(self.clay)
        h, s, v = hue(mat.get("baseColor", "#ffffff"))
        self.clock.check(h is not None and 12 <= h <= 40 and s > 0.5, f"the body is orange ({mat.get('baseColor')})")
        self.clock.cur["bodyColour"] = mat.get("baseColor")
        # the eye: a click on it, Material ▾ Glossy, then black
        if not getattr(self, "eye", ""):
            return
        t = self.hand.click(self.at(*self.eye_at), 0.7)
        self.clock.feedback("the eye selected", t, lambda: self.b.selected in self.eyes)
        self.clock.check(self.b.selected in self.eyes, f"a click on the eye selects it ({self.b.selected})")
        W.pump(0.3)
        if self.click("materialField", "the eye's Material ▾"):
            W.pump(0.4)
            starts = named(self.root, "matstart:")
            self.clock.cur["materialStarts"] = sorted(starts)
            glossy = next((n for n in starts if "gloss" in n.lower()), "")
            self.clock.check(bool(glossy), f"Glossy is in the Material list ({sorted(starts)})")
            if glossy:
                self.click(glossy, "Glossy")
                self.clock.wait(self.settled, "the glossy eye drawn")
        if W.find(self.root, "row:baseColor") is None:
            self.clock.stumble("the eye's new Glossy material shows no Base colour square", "MaterialRow.qml", 2)
        elif self.swatch("row:baseColor"):
            self.pick(None, 0.0, 0.03)
        mat = self.material(self.eye)                       # the copy follows its original (its `mirror`)
        self.clock.cur["eyeMaterial"] = {k: mat.get(k) for k in ("id", "name", "start", "baseColor", "roughness", "metallic")}
        copies = [e for e in self.eyes if self.doc.item(e).get("mirror") == self.eye]
        self.clock.check(len(copies) == 1, "the other eye is the mirrored copy, so it takes the same material")
        _, _, val = hue(mat.get("baseColor", "#ffffff"))
        self.clock.check(val < 0.12, f"the eye is black ({mat.get('baseColor')})")
        self.clock.check((mat.get("roughness") if mat.get("roughness") is not None else 1) < 0.3,
                         f"the eye shines (Glossy: roughness {mat.get('roughness')})")
        self.clock.wait(self.settled, "the colours drawn")

    def s8_wave(self):
        t = self.hand.click(self.at(0.0, 0.35), 0.6)       # the body again (the eye is selected): Pose needs the clay
        self.clock.feedback("the body selected", t, lambda: self.b.selected == self.clay)
        self.clock.feedback("Pose offered in the rail", t, lambda: W.find(self.root, "rail_pose") is not None, 5)
        t = self.click("rail_pose", "the rail's Pose")
        if t is None:
            return
        pose = self.v.pose
        self.clock.feedback("Pose on (joints shown)", t, lambda: pose.on and len(pose.dots) > 0, 20)
        self.clock.check(pose.on and pose.joints > 0, f"Pose on, the joints found ({pose.joints})")
        self.clock.cur["joints"] = sorted(bones(self.doc.item(self.clay)))
        for side in (1, -1):
            at = QPointF(self.cx + side * 0.45 * self.rx, self.cy + self.ry + 0.005 * self.h)
            n0 = len(self.doc.item(self.clay).get("holds") or [])
            t = self.hand.click(at, 0.6)
            self.clock.feedback("a foot held (ring)", t, lambda: len(self.doc.item(self.clay).get("holds") or []) > n0)
        holds = self.doc.item(self.clay).get("holds") or []
        self.clock.cur["holds"] = holds
        self.clock.check(len(holds) == 2, f"both feet held ({holds})")
        rest = {k: [b.get(f) for f in ("rx", "ry", "rz")] + [len(b.get("keys") or [])] for k, b in bones(self.doc.item(self.clay)).items()}
        # the character's right hand: the screen-left arm's tip (the mirror of the arm drawn on the right)
        tip = self.arm_pts(1)[len(self.arm_pts(1)) // 2 + 1]
        hand = QPointF(2 * self.cx - tip.x(), tip.y())
        lines = [{"id": ln.get("id"), "a": ln.get("a"), "b": ln.get("b")} for ln in pose.lines]
        self.clock.cur["lines"] = lines
        fr = next((ln for ln in lines if str(ln["id"]).endswith("forearm.R") or ln["id"] == "forearm.R"), None)
        if fr is not None:
            x, y, w, h = self.vp
            hand = QPointF(x + fr["b"][0] * w, y + fr["b"][1] * h)
        n0 = self.changes()
        pts = [QPointF(hand.x() + 0.05 * self.h * i / 30, hand.y() - 0.28 * self.h * i / 30) for i in range(31)]
        chips = []
        t = self.hand.drag(pts, 1.2, rest=0.3, on_move=lambda i: chips.append(pose.chip))
        self.clock.release("the wave drag: its change", t, lambda: self.changes() > n0)
        self.clock.release("the wave drag: the picture", t, self.settled)
        self.clock.cur["chips"] = chips[::5]
        after = {k: [b.get(f) for f in ("rx", "ry", "rz")] + [len(b.get("keys") or [])] for k, b in bones(self.doc.item(self.clay)).items()}
        moved = sorted(k for k in after if after[k] != rest.get(k))
        self.clock.cur["moved"] = moved
        self.clock.check({"arm.R", "forearm.R"} <= set(moved), f"the right arm bends at the shoulder and elbow ({moved})")
        self.clock.check(not ({"foot.L", "foot.R"} & set(moved)), "the held feet stay")
        self.clock.check(self.changes() == n0 + 1, f"the wave is one undo step ({n0} -> {self.changes()})")
        if {"chest", "body"} & set(moved):
            stuck = [e for e in self.eyes if self.doc.item(e).get("stick") or self.doc.item(e).get("parent")]
            if not stuck:
                self.clock.stumble(f"the wave also bends the upper body ({sorted({'chest', 'body'} & set(moved))}) but the eyes "
                                   "(separate spheres) stay where they were: they float off the tilted face",
                                   "apps/3d/app/screen3d/adding.py:147 place_at (a part placed on a clay is not stuck to it, "
                                   "so the clay's pose doesn't carry it)", 2)

    def s9_light(self):
        self.hand.key(Qt.Key_Escape)                       # (leaves Pose, as a person would before the next tool)
        W.pump(0.3)
        self.click("rail_lights", "the rail's Lights")
        tile = self.control("fly_light:rect", "Lights › Soft light")
        if tile is None:
            return
        before = {l["id"] for l in items_of(self.doc, "light")}
        t = self.hand.click_item(tile, 0.4)
        self.clock.feedback("the soft light added", t, lambda: len(items_of(self.doc, "light")) > len(before))
        new = [l for l in items_of(self.doc, "light") if l["id"] not in before]
        self.clock.check(len(new) == 1 and new[0].get("kind") == "rect", f"one soft light ({[l.get('kind') for l in new]})")
        if not new:
            return
        was, n0 = json.dumps(new[0], sort_keys=True), self.changes()
        t = self.hand.click(self.at(-0.3, -0.35), 0.7)
        self.clock.feedback("the light placed on the cheek", t, lambda: self.changes() > n0 or self.v.status.startswith("Error"))
        self.clock.wait(self.settled, "the lit picture")
        now = self.doc.item(new[0]["id"])
        self.clock.check(json.dumps(now, sort_keys=True) != was, "the click on the cheek moved and aimed the light")
        self.clock.cur["light"] = {k: now.get(k) for k in ("x", "y", "z", "intensity", "brightness")}

    def s10_angle(self):
        self.hand.key(Qt.Key_Escape)
        cams = {c["id"]: json.dumps(c, sort_keys=True) for c in items_of(self.doc, "camera")}
        x, y, w, h = self.vp
        p0 = QPointF(x + 0.85 * w, y + 0.3 * h)                 # a short turn: a little to the side, a little above
        pts = [QPointF(p0.x() - 2.5 * i, p0.y() + 1.2 * i) for i in range(31)]
        t = self.hand.drag(pts, 1.0, button=Qt.RightButton, rest=0.2)
        self.clock.feedback("the view turned", t, lambda: self.v.mode == "free")
        self.clock.check(self.v.mode == "free", f"a right-drag turned the view ({self.v.mode})")
        btn = self.control("takeShot", "Make this the shot")
        if btn is None:
            return
        self.hand.glide(QPointF(W.centre(btn)), 0.7)
        W.pump(0.6)                                          # a hover shows the frame it would take
        n0 = self.changes()
        t = self.hand.click_item(btn, 0.1)
        self.clock.feedback("the shot taken", t, lambda: self.changes() > n0)
        self.clock.wait(self.settled, "the shot's picture")
        now = {c["id"]: json.dumps(c, sort_keys=True) for c in items_of(self.doc, "camera")}
        self.clock.check(now != cams, "Shot 1's camera moved")
        self.clock.check(self.v.mode == "shot", f"the view is on the shot again ({self.v.mode})")
        cam = next((json.loads(now[k]) for k in now if now[k] != cams.get(k)), {})
        self.clock.cur["camera"] = {k: cam.get(k) for k in ("x", "y", "z", "rx", "ry", "rz")}

    def s11_render(self):
        x, y, w, h = self.vp
        heads = [c for c in all_items(self.root) if c.property("text") == "Render" and visible(c)
                 and c.mapToScene(QPointF(0, 0)).y() < y]
        btn = max(heads, key=lambda c: c.mapToScene(QPointF(0, 0)).x(), default=None)   # the blue button, not the page tab
        if not self.clock.check(btn is not None, "the header's Render button is on screen"):
            return
        if not btn.objectName():
            self.clock.stumble("the header's Render button has no objectName (found by its text)",
                               "apps/3d/app/qml/RenderButton.qml:15", 1)
        ex = self.b.exporter
        t = self.hand.click_item(btn)
        self.clock.feedback("the render sheet", t, lambda: ex.open)
        est = W.find(self.root, "estimateText")
        t = time.perf_counter()
        told = W.pump(30, lambda: est is not None and "measur" not in str(est.property("text")).lower(), "the estimate")
        if not told:
            W.FAILS.pop()                                   # (a slow estimate is a stumble, not a failed check)
        self.clock.cur["appWait"] += time.perf_counter() - t
        self.clock.cur["estimate"] = str(est.property("text")) if est is not None else ""
        if not told:
            self.clock.stumble(f"the sheet still says {self.clock.cur['estimate']!r} after 30 s: no time before it starts",
                               "apps/3d/app/screen3d/estimate_sheet.py (waits for a free graphics card)", 2)
        W.pump(0.5)
        go = by_text(self.root, ex.actionText)
        if not self.clock.check(go is not None, f"the sheet's {ex.actionText!r} button"):
            return
        self.clock.stumble(f"Render opens a sheet first; the picture needs a second click ({ex.actionText!r})",
                           "apps/3d/app/screen3d/export3d.py:63 openFor (SPEC § 1: Render makes the picture)", 1)
        quality = next((x.get("renderQuality", "") for x in self.doc.data.get("shots", []) if x["id"] == self.b.shot_id), "")
        self.clock.cur["quality"] = quality or "(the default)"
        if quality != "final":
            self.clock.stumble(f"Render makes a {quality or 'default (Good)'} picture, not the final quality SPEC § 1 says",
                               "apps/3d/python/rostrum3d/render_fields.py (the shot's default renderQuality)", 1)
        started = lambda: ex.state in ("running", "done", "failed") or self.b.renderJob.state == "running"  # noqa: E731
        for attempt in range(2):
            go = by_text(self.root, ex.actionText) or go
            p = go.mapToScene(QPointF(0, 0))
            self.clock.cur.setdefault("goAt", []).append([round(p.x()), round(p.y()), round(go.width()), round(go.height()),
                                                           go.metaObject().className()])
            t = self.hand.click_item(go)
            if W.pump(4, started):
                break
            self.clock.stumble("a click on the sheet's Render button started nothing (clicked again)",
                               "shared/gui-kit/qml/RostrumKit/ExportSheet.qml:134 (footer Button)", 3)
        self.clock.feedback("the render started", t, started, 5)
        self.clock.wait(lambda: ex.state in ("done", "failed", "cancelled"), "the render", 600)
        self.clock.check(ex.state == "done", f"the render finished ({ex.state}: {ex.note})")
        path = ex.path
        self.clock.cur["render"] = {"path": path, "note": ex.note}
        self.clock.check(bool(path) and Path(path).exists(), f"the render file exists ({path})")
        self.clock.check(by_text(self.root, "Show in folder") is not None, "Show in folder is one click away")
        if path and Path(path).exists():
            shutil.copyfile(path, OUT / ("11-render-file" + Path(path).suffix))

    def run(self):
        steps = [self.s1_clay, self.s2_body, self.s3_arm, self.s4_feet, self.s5_shape, self.s6_eye, self.s7_colour,
                 self.s8_wave, self.s9_light, self.s10_angle, self.s11_render]
        for n, (fn, (name, budget)) in enumerate(zip(steps, BUDGET), 1):
            if n > UNTIL:
                break
            self.clock.begin(n, name, budget)
            try:
                fn()
            except Exception as e:  # noqa: BLE001  a step that crashed is a failed check, the walk stops
                self.clock.check(False, f"{name} stopped: {type(e).__name__}: {e}")
                self.clock.cur.setdefault("onScreen", named(self.root))
                self.clock.end(self.picture(n, name + "-crash"))
                raise
            self.clock.end(self.picture(n, name))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-cl7-"))
    app = qt_app()
    doc = files_3d.blank(project)
    screen = W.app3d.Screen(W.SIZE)
    report = {"spec": "3d-simplicity SPEC § 1", "size": list(W.SIZE)}
    walk = rec = None
    try:
        screen.show(doc, autosave=True)
        W.pump(60, screen.ready, "the first picture")
        W.pump(30, lambda: D.settled(screen.bridge.viewport), "the first picture to settle")
        walk = Walk(screen, report)
        if RECORD:
            rec = Recorder(screen.win, walk.hand, SCRATCH)
            walk.clock.rec = rec
            rec.start()
        W.pump(1.0)
        walk.run()
        W.pump(2.0)                                          # the picture stays on screen a moment in the video
    except Exception as e:  # noqa: BLE001  a crash is a failed walk, said with its reason
        W.FAILS.append(f"the walk stopped: {type(e).__name__}: {e}")
    finally:
        if rec is not None:
            rec.stop()
        steps = walk.clock.steps if walk else []
        report["steps"] = steps
        report["table"] = [{"n": s["n"], "step": s["name"], "budgetS": s["budget"], "realS": s["realS"],
                            "appWaitS": s["appWaitS"], "checks": "pass" if all(c["ok"] for c in s["checks"]) else "FAIL",
                            "stumbles": len(s["stumbles"])} for s in steps]
        report["totalS"] = round(sum(s["realS"] for s in steps), 1)
        report["appWaitTotalS"] = round(sum(s["appWaitS"] for s in steps), 1)
        report["underFiveMinutes"] = report["totalS"] < 300
        report["releases"] = [{"step": s["n"], **r} for s in steps for r in s["releases"]]
        report["quiet"] = [{"step": s["n"], **f} for s in steps for f in s["feedback"] if f["quiet"]]
        report["slowReleases"] = [{"step": s["n"], **r} for s in steps for r in s["releases"] if r["slow"]]
        report["stumbles"] = sorted(({"step": s["n"], **x} for s in steps for x in s["stumbles"]), key=lambda x: -x["weight"])
        if steps and len(steps) == len(BUDGET) and not report["underFiveMinutes"]:
            W.FAILS.append(f"the human-paced total is {report['totalS']} s, not under 5:00")
        if rec is not None:
            report["video"] = rec.encode(OUT / "cl7-five-minutes.mp4", OUT / "cl7-five-minutes-share.mp4")
        report["fails"] = W.FAILS
        (OUT / "cl7_walk.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
        screen.close()
        W.pump(1.0)
        shutil.rmtree(project, ignore_errors=True)
    print(f"\n{'step':<22}{'budget':>8}{'real':>8}{'app wait':>10}  checks")
    for r in report["table"]:
        print(f"{r['n']:>2} {r['step']:<19}{r['budgetS']:>7}s{r['realS']:>7}s{r['appWaitS']:>9}s  {r['checks']}"
              f"{'  stumbles: ' + str(r['stumbles']) if r['stumbles'] else ''}")
    print(f"total {report['totalS']} s (app waits {report['appWaitTotalS']} s)")
    print(f"{len(W.FAILS)} failed check(s); pictures and cl7_walk.json in {OUT}")
    for f in W.FAILS:
        print("  " + f)
    app.quit()
    return 1 if W.FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
