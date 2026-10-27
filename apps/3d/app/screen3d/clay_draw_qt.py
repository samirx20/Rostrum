"""Draw and Spin on the viewport (3d-simplicity SPEC § 1 0:00–1:40, § 3.1; CL3 CONTRACT § 5), for QML as
`viewport.clay.drawer` (ClayDraw.qml). The Clay tool's Make tiles Draw (chosen when the tool turns on) and Spin.

- Draw: a left drag draws an outline (it never turns the view); the line follows the pointer, and a chip 16 px below-
  right of it says the outline's size ("18 × 30 cm") on the plane it will lie on. While armed, the clay under the
  pointer has the thin hover outline (the view request's `hovered`, `outlined`): drawn from there, the shape joins it.
- Spin: a vertical line stands at the pointer (the axis); the drag from it draws half a profile.
- Release: the press's pick decides the plane (clay_draw.plane_for) and the pixels become points on it: on a clay,
  `clay.draw` / `clay.spin` on that clay in its own space; elsewhere `clay.add(draw=…)` / `clay.add(spin=…)` in the
  scene. One change, one undo step; the clay is selected after. (A click or a scribble: the operation makes a lump.)
- From the release until the new clay is in the picture (the engine builds it: a second or two), the outline stays on
  the viewport, closed and filled with a clay grey (`landing`), so the release reacts at once (common brief, speed vs.
  interaction); the operation runs a frame after the release, once that is drawn.
- Esc mid-drag (esc3d.py), or the drag taken away: the line goes, nothing changes, no undo step.
The whole drag uses the scene and camera of its press; the press's pick is asked at once and the release waits for it.
Picks go to the viewport's engine thread, the newest hover only (as the brush ring's).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from . import clay_draw as D
from . import clay_ring as R
from .gizmo import View

MIN_STEP = 2.0               # logical px between kept points of the line
LANDING_MAX_MS = 8000        # the filled outline goes then at the latest (a picture that never comes is said elsewhere)


class ClayDraw(QObject):
    changed = Signal()
    lineChanged = Signal()
    answered = Signal(object)        # (what, number, pick answer or error line, scene, request) from the engine thread

    def __init__(self, tool):
        super().__init__(tool)
        self.t = tool
        self._pts, self._down, self._up, self._drag, self._start = [], False, True, 0, None
        self._hover, self._hover_busy, self._hover_next = 0, False, None
        self._join, self._axis, self._chip, self._dpr = "", [], "", 1.0
        self._scene = self._cam = self._view = None
        self._landing, self._landed_wait = [], False
        self._landing_max = QTimer(self, singleShot=True, interval=LANDING_MAX_MS, timeout=self._landing_gone)
        self.answered.connect(self._on_answer)
        tool.changed.connect(self.changed)
        if (pictures := getattr(tool.v, "serialChanged", None)) is not None:     # (a test's stand-in viewport has none)
            pictures.connect(self._on_picture)

    # --- what QML reads
    on = Property(bool, lambda s: s.t.draws, notify=changed)
    mode = Property(str, lambda s: s.t.tool if s.t.draws else "", notify=changed)
    line = Property("QVariantList", lambda s: [list(p) for p in s._pts], notify=lineChanged)     # logical px
    chip = Property(str, lambda s: s._chip, notify=lineChanged)
    axis = Property("QVariantList", lambda s: s._axis, notify=lineChanged)      # Spin: parts of the picture
    joining = Property(str, lambda s: s._join, notify=lineChanged)               # the clay under the pointer
    landing = Property("QVariantList", lambda s: [list(p) for p in s._landing], notify=lineChanged)   # released, not yet built
    landingFilled = Property(bool, lambda s: s.t.tool != "spin", notify=lineChanged)                 # Draw fills; Spin is a profile

    @property
    def drawing(self) -> bool:
        return self._down

    def outlined(self) -> list[str]:
        """The clay the viewport outlines while Draw / Spin is armed: the one a drag from here would join."""
        return [self._join] if self._join and self.t.draws else []

    def _v(self):
        return self.t.v

    def _is_clay(self, item_id) -> bool:
        doc = self.t.b.doc
        return bool(item_id) and doc.has(item_id) and doc.item(item_id).get("type") == "clay"

    def _picture(self, x, y):
        """Logical px → the engine picture's px."""
        k = self._dpr * self._v()._scale
        return x * k, y * k

    def _ask(self, what, n, x, y, scene=None, cam=None):
        v = self._v()
        if scene is None:
            scene, cam = v.sent()
        px, py = self._picture(x, y)
        req = {**cam, "x": round(px), "y": round(py)}

        def job(eng):
            try:
                eng.ensure_scene(scene)
                self.answered.emit((what, n, eng.pick(**req), scene, req))
            except Exception as e:  # noqa: BLE001  said on the status line
                self.answered.emit((what, n, str(e), scene, req))
        v._r.call(job)

    def _on_answer(self, a):
        what, n, r, scene, req = a
        if what == "hover":
            return self._hovered(n, r, scene, req)
        if n != self._drag:
            return                                          # a dropped drag's
        self._start = r
        if isinstance(r, str):
            self.t.b.fail_line(f"Error: clay: {r}")
        if self._up and self._pts:
            self._finish()

    # --- hover: the clay a drag would join, Spin's axis
    @Slot(float, float, float)
    def hover(self, x, y, dpr):
        if not self.t.draws or self._down or self._v()._size is None:
            return
        self._dpr = dpr
        if self._hover_busy:
            self._hover_next = (x, y)
            return
        self._hover_busy, self._hover = True, self._hover + 1
        self._ask("hover", self._hover, x, y)

    @Slot()
    def unhover(self):
        self._hover += 1
        if not self._down:
            self._set_join("")
            if self._axis:
                self._axis = []
                self.lineChanged.emit()

    def _hovered(self, n, r, scene, req):
        self._hover_busy = False
        if n == self._hover and not self._down and not isinstance(r, str):
            hit = bool(r.get("hit"))
            self._set_join(r["item"] if hit and self._is_clay(r.get("item")) else "")
            self._axis = self._axis_at(r, scene, req) if self.t.tool == "spin" else []
            self.lineChanged.emit()
        if self._hover_next is not None:
            nxt, self._hover_next = self._hover_next, None
            self.hover(*nxt, self._dpr)

    def _axis_at(self, r, scene, req):
        view = View.of(req, scene, req["frame"], req["width"], req["height"])
        point = r["point"] if r.get("hit") else (D.ground_hit(view, req["x"], req["y"]) or (None,))[0]
        if point is None:
            return []
        return D.axis_line(view, point, self._dpr * self._v()._scale)

    def _set_join(self, clay):
        if clay != self._join:
            self._join = clay
            self.lineChanged.emit()
            self._v().redraw()                              # its outline comes or goes

    # --- the drag: logical px from QML
    @Slot(float, float, float)
    def press(self, x, y, dpr):
        v = self._v()
        if not self.t.draws or v._size is None:
            return
        self._drag += 1
        self._dpr, self._down, self._up, self._start, self._pts = dpr, True, False, None, [(x, y)]
        self._scene, self._cam = v.sent()                  # one scene and camera for the whole drag
        self._view = View.of(self._cam, self._scene, self._cam["frame"], self._cam["width"], self._cam["height"])
        self._ask("press", self._drag, x, y, self._scene, self._cam)
        self._chip = ""
        self.lineChanged.emit()

    @Slot(float, float)
    def move(self, x, y):
        if not self._down:
            return
        lx, ly = self._pts[-1]
        if abs(x - lx) + abs(y - ly) < MIN_STEP:
            return
        self._pts.append((x, y))
        self._chip = self._size_now()
        self.lineChanged.emit()

    @Slot()
    def release(self):
        if not self._down:
            return
        self._down, self._up = False, True
        if self._start is not None:
            self._finish()

    @Slot()
    def cancel(self):
        """Esc mid-drag, or the drag taken away: the line goes, nothing changes."""
        if self._down or (self._up and self._pts):
            self._drag += 1                                 # its pick's answer is dropped
            self._down, self._up, self._pts, self._chip, self._start = False, True, [], "", None
            self.lineChanged.emit()

    # --- inside
    def _px(self):
        return [self._picture(x, y) for x, y in self._pts]

    def _plane(self, pts_px):
        start = self._start if isinstance(self._start, dict) else None
        return D.plane_for(self._view, start, pts_px, self._is_clay)

    def _size_now(self) -> str:
        if len(self._pts) < 3:
            return ""
        pts_px = self._px()
        plane = self._plane(pts_px)
        if plane is None:
            return ""
        return D.size_text(D.lift(self._view, pts_px, plane[0], plane[1]), plane[1])

    def _finish(self):
        """The release, its press's pick known: the operation worked out now (the drag's own scene and view), the
        outline kept on screen filled, and the operation applied a frame later, once that is drawn."""
        b, mode, pts_px, line = self.t.b, self.t.tool, self._px(), list(self._pts)
        self._pts, self._chip = [], ""
        self.lineChanged.emit()
        if isinstance(self._start, str):
            return                                          # the pick failed: said already
        plane = self._plane(pts_px)
        if plane is None:
            return b.fail_line("Error: clay: draw over the ground or on a clay, with the view not looking straight down.")
        origin, normal, clay = plane
        pts = D.lift(self._view, pts_px, origin, normal)
        if not pts:
            return b.fail_line("Error: clay: that outline is off the plane it would stand on; draw it over the ground.")
        call, label = self.calls(mode, pts, normal, clay)
        self._landing, self._landed_wait = line, False
        self._landing_max.start()
        self.lineChanged.emit()
        QTimer.singleShot(30, lambda: self._make(call, label, clay))

    def _make(self, call, label, clay):
        """One operation, one undo step; then the clay selected, the outline kept until the picture shows it."""
        b = self.t.b
        before = set(self.t._all_clays())
        if not b._guard(lambda: b._apply([call], label)):
            return self._landing_gone()
        self._landed_wait = True                            # the next settled picture takes the outline away
        new = clay or next((c for c in self.t._all_clays() if c not in before), "")
        if new and b.doc.has(new):
            b.select(new)

    def _landing_gone(self):
        self._landing_max.stop()
        if self._landing:
            self._landing, self._landed_wait = [], False
            self.lineChanged.emit()

    def _on_picture(self):
        """A new viewport picture: once the engine holds no newer scene to load, the new clay is in it."""
        r = getattr(self._v(), "_r", None)
        if self._landed_wait and not getattr(r, "_loading", False) and getattr(r, "_want", None) is None:
            self._landing_gone()

    def calls(self, mode, pts, normal, clay):
        """(the operation, its History name) for world points `pts` on a plane facing `normal`, joining `clay` or new."""
        word = "Spin" if mode == "spin" else "Draw"
        if clay:
            scene, frame = self._scene, self._cam["frame"]
            to = lambda p: R.to_clay(scene, clay, frame, p)  # noqa: E731
            own = [to(p) for p in pts]
            args = {"profile": own} if mode == "spin" else {"outline": own,
                                                            "facing": D.direction_into(to, pts[0], normal)}
            name = self.t.b.label_of(self.t.b.doc.item(clay))
            return {"op": f"clay.{mode}", "target": [clay], "args": args}, f"{word} on {name}"
        args = {"spin": pts} if mode == "spin" else {"draw": pts, "facing": [round(c, 6) for c in normal]}
        return {"op": "clay.add", "target": [], "args": args}, "New clay"
