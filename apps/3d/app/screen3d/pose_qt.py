"""The Pose tool on screen, for QML as `viewport.pose` (3d-simplicity SPEC § 4, CL5 contract § C). Pose shows in the
rail on the Build and Animate pages whenever one clay is selected (Shift+P); choosing it on a clay with no joints, or
joints found before its shape changed, finds them first (`pose.find_joints`, one undo step). Pose is on at the click
(the rail, the panel) and `finding` says "Finding joints…" on the viewport and in the panel from the same frame; the
check and the finding run after that frame is drawn, so a click is never a second of nothing (common brief, speed vs.
interaction). While Pose is on, the clay's bones are drawn thin (Pose.qml), posed at the playhead, a small dot on each
joint and an orange ring on each hold; nothing of them shows otherwise. Hovering the clay lights the bones a drag there
would turn (from the engine's pick: pose_link.bone_at, pose_view.moving). The pointer itself is pose_drag.py's.
Selecting something else, V, Q, B or Esc leaves Pose. Agents do all of it with the same operations (ops_pose).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from rostrum3d import aim, through

from . import pose_link as L, pose_view as PV
from .pose_drag import PoseDrag
from .pose_solver import Solver

NAMES = ("plain", "humanoid")
CHIP_MS = 600                    # the chip stays this long after the release (CANVAS § 3.8)


class Pose(PoseDrag, QObject):
    changed = Signal()
    drawn = Signal()                 # the overlay (bones, joints, holds, chip, pointer): per pointer result, never the rail
    toggled = Signal()               # Pose on or off (the gizmo hides while it is on)
    menuAt = Signal(float, float)    # a right click (no drag) at logical px: the right-click menu opens there
    answered = Signal(object)        # (number, kind, pick answer or error line, scene, request, extra) from the engine
    solved = Signal(object)          # a pose drag's solver result (pose_solver.py), from its thread
    gridded = Signal(object)         # (clay id, its clay_grid reply or an error line) from the engine's thread

    def __init__(self, bridge, viewport):
        super().__init__(viewport)
        self.b, self.v = bridge, viewport
        self.gridded.connect(self._on_grid)
        self.timings = []                # the last drag's per-result times (ms): ik, pose, overlay, solve, apply, round
        self.solver = Solver(self.solved.emit)
        self.solved.connect(self._on_solved)
        self._on, self._id, self._lines, self._dots, self._rings, self._lit = False, "", [], [], [], set()
        self._chip, self._cursor, self._dpr, self._n, self._hover_busy, self._hover_next = "", "pick", 1.0, 0, False, None
        self._held, self._hover_ring, self._finding = [], -1, False
        self._chip_timer = QTimer(self, singleShot=True, interval=CHIP_MS, timeout=self._chip_gone)
        self._drag_reset()
        self.answered.connect(self._on_answer)
        viewport.serialChanged.connect(self._refresh)
        for s in (bridge.docChanged, bridge.docStepped):        # counts, names: the panel and the rail follow
            s.connect(lambda *_: (self.changed.emit(), self._refresh()))
        bridge.frameChanged.connect(self._refresh)
        bridge.selectionChanged.connect(self._on_selection)
        bridge.pageChanged.connect(lambda *_: self.changed.emit())
        hub = getattr(bridge, "_hub", None)
        if hub is not None:
            self.toggled.connect(hub.refresh)        # the right-click menu's Pose entries follow the tool
        for tool in (viewport.paint, viewport.clay_tool, viewport.mesh_edit):     # another tool on: Pose goes
            tool.changed.connect(lambda t=tool: self.leave() if t.on else None)

    on = Property(bool, lambda s: s._on, notify=changed)
    can = Property(bool, lambda s: s._selected_clay() is not None, notify=changed)       # the rail offers Pose
    dragging = Property(bool, lambda s: bool(s._phase), notify=drawn)
    lines = Property("QVariantList", lambda s: s._lines, notify=drawn)    # [{a, b, id, lit}] parts of the viewport
    dots = Property("QVariantList", lambda s: s._dots, notify=drawn)      # [{p, id, joint}]
    rings = Property("QVariantList", lambda s: s._rings, notify=drawn)    # [{p, bone}]
    chip = Property(str, lambda s: s._chip, notify=drawn)                 # "forearm.R · 64°" during a drag
    cursor = Property(str, lambda s: s._cursor, notify=drawn)             # the kit pointer's kind: pick / rotate
    itemName = Property(str, lambda s: s.b.label_of(s._item()) if s._item() else "", notify=changed)
    joints = Property(int, lambda s: len(PV.chain_of(s._item() or {})), notify=changed)
    holds = Property(int, lambda s: len((s._item() or {}).get("holds") or []), notify=changed)
    names = Property(str, lambda s: (s._item() or {}).get("jointNames", "plain"), notify=changed)
    finding = Property(bool, lambda s: s._finding, notify=changed)       # "Finding joints…" on the viewport and the panel

    def _found(self):
        if self._finding:
            self._finding = False
            self.changed.emit()

    # --- the clay posed
    def _item(self):
        if not self._id or not self.b.doc.has(self._id):
            return None
        it = self.b.doc.item(self._id)
        return it if it.get("type") == "clay" else None

    def _selected_clay(self):
        sel = self.b.selection
        it = self.b.doc.item(sel[0]) if len(sel) == 1 and self.b.doc.has(sel[0]) else None
        return it if it is not None and it.get("type") == "clay" else None

    # --- the tool
    @Slot()
    def toggle(self):
        self.leave() if self._on else self.enter()

    @Slot()
    def enter(self):
        it = self._selected_clay()
        if it is None:
            return self.b.fail_line("Pose needs one clay selected.")
        self.v.clay_tool.leave()
        self.v.paint.leave()
        self.v.mesh_edit.leave()
        self._on, self._id = True, it["id"]
        self._finding = not it.get("bones")             # no joints yet: say so at once, before any work
        self.toggled.emit()
        self.changed.emit()
        self._refresh()
        QTimer.singleShot(30, self._check)              # after this frame is drawn: Pose shows on at the click

    def _check(self):
        """Pose's first work, a frame after the click: are the joints out of date? Then find them."""
        it = self._item()
        if not self._on or it is None:
            return self._found()
        try:
            stale = L.out_of_date(it, self.b.doc.data)
        except Exception as e:  # noqa: BLE001  the joint finder isn't there or failed: said, Pose stays on
            self._found()
            return self.b.fail_line(f"Error: pose: {e}")
        if not stale:
            return self._found()
        self.b.say("Finding joints…")
        if not self._finding:
            self._finding = True
            self.changed.emit()
            return QTimer.singleShot(30, self.findAgain)      # the state shows before the engine works
        self.findAgain()

    @Slot()
    def leave(self):
        if self._on:
            self.cancel()
            self._on, self._id, self._lit, self._chip, self._finding = False, "", set(), "", False
            self.toggled.emit()
            self.changed.emit()
            self._refresh()

    @Slot()
    def findAgain(self):
        """The clay's grid from the window's own view first (on the engine's thread: the screen's thread never waits
        for it, as the view answers there), then pose.find_joints with that grid, one undo step."""
        it = self._item()
        if it is None:
            return self._found()
        if not self._finding:                           # Find again in the panel: the same state while it works
            self._finding = True
            self.changed.emit()
        scene, cid = self.v.sent()[0], it["id"]

        def job(eng):
            try:
                eng.ensure_scene(scene)
                self.gridded.emit((cid, eng.clay_grid(cid, L.CELLS)))
            except Exception as e:  # noqa: BLE001  said on the status line
                self.gridded.emit((cid, str(e)))
        self.v._r.call(job)

    def _on_grid(self, answer):
        cid, grid = answer
        it = self._item()
        if isinstance(grid, str):
            self._found()
            return self.b.fail_line(f"Error: pose: the joints could not be found: {grid}")
        if it is None or it["id"] != cid:
            return self._found()
        with L.grid_given(grid):
            if self.b._guard(lambda: self.b._apply(L.find_calls(cid), f"Find joints of {self.itemName}")):
                self.b.say("")
        self._found()

    @Slot(str)
    def setNames(self, names):
        it = self._item()
        if it is not None and names in NAMES and names != self.names:
            self.b._guard(lambda: self.b._apply(L.names_calls(it["id"], names), f"Joint names: {names.title()}"))

    @Slot()
    def clearHolds(self):
        it = self._item()
        if it is not None and it.get("holds"):
            calls = [c for h in it["holds"] for c in L.hold_calls(it["id"], rest=h, off=True)]
            self.b._guard(lambda: self.b._apply(calls, "Clear holds"))

    def rest(self):
        """Pose: back to rest. Build page: every turn of the shot; Animate: the rest keyed at the playhead."""
        it = self._item()
        at = self.b.time if self.b._page == "animate" else None
        if it is not None:
            self.b._guard(lambda: self.b._apply(L.rest_calls(it["id"], at), "Pose: back to rest"))

    def delete_hovered(self) -> bool:
        """Del: the hold ring under the pointer let go (True when there was one)."""
        if self._phase or self._hover_ring < 0 or self._hover_ring >= len(self._rings):
            return False
        self._let_go(self._rings[self._hover_ring])
        return True

    def _on_selection(self, *_):
        if self._on and self.b.selected != self._id:
            self.leave()
        self.changed.emit()

    # --- the hover: rings and dots by their place, the part by the engine's pick (newest only)
    @Slot(float, float, float)
    def hover(self, x, y, dpr):
        if not self._on or self._phase or self.v._size is None:
            return
        self._dpr = dpr
        px, py = self._px(x, y)
        self._hover_ring = PV.near(self._rings, px, py, *self.v._size, PV.RING_HIT * self._k())
        if self._hover_busy:
            self._hover_next = (x, y)
            return
        self._hover_busy = True
        self._ask(x, y, "hover")

    @Slot()
    def unhover(self):
        self._n += 1
        self._hover_ring, self._hover_busy, self._hover_next = -1, False, None
        if self._lit and not self._phase:
            self._lit = set()
            self._refresh()

    def _ask(self, x, y, kind, extra=None):
        scene, cam = self.v.sent()
        px, py = self._px(x, y)
        req = {**cam, "x": round(px), "y": round(py)}
        self._n += 1
        n = self._n

        def job(eng):
            try:
                eng.ensure_scene(scene)
                self.answered.emit((n, kind, eng.pick(**req), scene, req, extra))
            except Exception as e:  # noqa: BLE001  said on the status line, never a silent no-op
                self.answered.emit((n, kind, str(e), scene, req, extra))
        self.v._r.call(job)

    def _on_answer(self, answer):
        n, kind, r, scene, req, extra = answer
        if kind in ("press", "ring"):                   # a failure ends the gesture, said on the status line
            fn = (lambda: self._on_press(r, scene, req)) if kind == "press" else (lambda: self._on_ring(r, scene, req, extra))
            return self.b._guard(fn) or self.cancel()
        self._hover_busy = False
        if n == self._n and not self._phase:
            self._lit_now = set()
            self.b._guard(lambda: self._lit_by(r, scene, req))
            if self._lit_now != self._lit:              # redrawn only when what would move changes
                self._lit = self._lit_now
                self._refresh()
        if self._hover_next is not None:
            nxt, self._hover_next = self._hover_next, None
            self.hover(*nxt, self._dpr)

    def _lit_by(self, r, scene, req):
        it = self._item()
        if it is None or isinstance(r, str) or not r.get("hit") or r.get("item") != it["id"]:
            return
        local = aim.point(aim.invert(through.find_item(scene, it["id"], req["frame"])[0]), r["point"])
        held = {h["bone"] for h in L.holds_of(it)}
        self._lit_now = set(PV.moving(PV.chain_of(it), L.bone_at(it, local, self.b.time), held))

    # --- drawing
    def _refresh(self, *_):
        if self._phase == "pose":
            return                                  # a drag draws its own bones (pose_drag._pose_to)
        if self._on and self._item() is None:
            return self.leave()
        self._draw(lit=self._lit)

    def _draw(self, turns=None, lit=()):
        was = (self._lines, self._dots, self._rings, getattr(self, "_cursor", None))
        self._lines, self._dots, self._rings = [], [], []
        it = self._item() if self._on else None
        if it is not None and self.v._size is not None and it.get("bones"):
            self.b._guard(lambda: self._place(it, turns, lit))
        self._cursor_now()
        if (self._lines, self._dots, self._rings, self._cursor) != was:     # a scrub step with Pose off draws nothing new
            self.drawn.emit()

    def _place(self, it, turns, lit):
        from .gizmo import View
        scene, cam = self.v.sent()
        w, h = self.v._size
        try:
            world = through.find_item(scene, it["id"], self.b.frame)[0]
        except ValueError:                          # not in the picture (hidden): nothing to draw
            return
        clay = self._clay0 or it
        drawn = PV.overlay(clay, L.holds_of(clay), world, View.of(cam, scene, self.b.frame, w, h), self.b.time, w, h,
                           lit, turns)
        self._lines, self._dots, self._rings = drawn["lines"], drawn["dots"], drawn["rings"]

    def _chip_gone(self):
        self._chip_timer.stop()
        if self._chip:
            self._chip = ""
            self.drawn.emit()

    def _cursor_now(self):
        self._cursor = "rotate" if self._phase == "orbit" else "pick"

    def _pointer(self):
        self._cursor_now()
        self.drawn.emit()
