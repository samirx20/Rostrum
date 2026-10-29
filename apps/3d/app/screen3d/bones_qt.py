"""Bones in the viewport, for QML as `viewport.bones` (SPEC §9, Animate rail › Bones, shown while a mesh is selected).

- **Placing a chain:** Bones starts it on the selected mesh; each click on the mesh adds a point (picked by the engine,
  the same pick as selecting), root first; Enter makes the chain with `bone.chain` (one undo step, the mesh bound),
  Backspace takes the last point back, Esc (or selecting something else) cancels.
- **Seeing the bones:** on the Animate page, the selected mesh's chain (or the chain of the selected bone) is drawn
  over the picture as thin diamonds from head to tail, posed at the playhead (skin.py's numbers, the ones the core
  bends the mesh with), projected through the same view as the gizmo (gizmo.View). A click near a drawn bone picks it
  before the mesh behind (`bone_at`, asked by the viewport's click); a selected bone gets turn rings (gizmo_bone.py).
Screen state only: the points being placed are not in the document until Enter.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication

from rostrum_core.keys import layers
from rostrum3d import aim, skin, through

from .gizmo import HIT, View, _seg_dist

HINT = "Click along the mesh, root first  ·  Enter makes the chain  ·  Backspace takes a point back  ·  Esc cancels"


class Bones(QObject):
    changed = Signal()
    answered = Signal(object)             # (mesh id, pick answer or error line) from the engine thread

    def __init__(self, viewport):
        super().__init__(viewport)
        self.v, self.b = viewport, viewport.bridge
        self.mesh, self.points, self._lines, self._dots = "", [], [], []
        self.answered.connect(self._apply)
        self.b.selectionChanged.connect(self._on_selection)
        viewport.serialChanged.connect(self._refresh)       # a new picture: a new frame, view or document
        self.b.docChanged.connect(self._refresh)            # a bone turned changes no picture on a mesh that can't bend
        self.b.docStepped.connect(self._refresh)            # (and follows a ring drag move by move)
        self.b.frameChanged.connect(self._refresh)
        self.b.pageChanged.connect(self._refresh)

    on = Property(bool, lambda s: bool(s.mesh), notify=changed)
    count = Property(int, lambda s: len(s.points), notify=changed)
    meshSelected = Property(bool, lambda s: s._selected_mesh() != "", notify=changed)    # the rail shows Bones then
    lines = Property("QVariantList", lambda s: s._lines, notify=changed)   # [{a, b}] in parts of the viewport (0..1)
    dots = Property("QVariantList", lambda s: s._dots, notify=changed)     # placed points, [x, y] in parts

    def _selected_mesh(self) -> str:
        sel = self.b.selected
        return sel if sel and self.b.doc.has(sel) and self.b.doc.item(sel).get("type") == "mesh" else ""

    @Slot()
    def start(self):
        mesh = self._selected_mesh()
        if not mesh:
            return self.b.fail_line("Error: bones: select the mesh to put bones in first.")
        self.mesh, self.points = mesh, []
        self.b.say(HINT)
        self._refresh()

    @Slot()
    def cancel(self):
        if self.mesh:
            self.mesh, self.points = "", []
            self.b.say("")
            self._refresh()

    @Slot()
    def back(self):
        if self.points:
            self.points.pop()
            self._refresh()

    @Slot()
    def make(self):
        if len(self.points) < 2:
            return self.b.fail_line("Error: bones: click at least two points along the mesh (one bone per pair).")
        mesh, pts = self.mesh, [list(p) for p in self.points]
        call = {"op": "bone.chain", "target": [mesh], "args": {"points": pts, "space": "mesh"}}
        self.mesh, self.points = "", []
        self.b.say("")
        self.b._guard(lambda: self.b._done(self.b.doc.apply([call], self.b.who, label="Make bone chain"), ""))
        self._refresh()

    def wants_click(self) -> bool:
        return bool(self.mesh) and self.b.selected == self.mesh and self.b.doc.has(self.mesh)

    def click(self, x: float, y: float):
        scene, cam = self.v._pick_at(x, y)
        mesh, frame = self.mesh, self.b.frame

        def job(eng):
            try:
                eng.ensure_scene(scene)
                self.answered.emit((mesh, {"hit": eng.pick(**cam), "scene": scene, "frame": frame}))
            except Exception as e:                          # loud, on the status line (never a silent no-op)
                self.answered.emit((mesh, str(e)))
        self.v._r.call(job)

    def _apply(self, answer):
        mesh, r = answer
        if isinstance(r, str):
            return self.b.fail_line(f"Error: bones: {r}")
        hit = r["hit"]
        if mesh != self.mesh:
            return
        if not hit.get("hit") or hit.get("item") != mesh:
            return self.b.fail_line(f"Error: bones: click on {mesh} itself to place a point.")
        world = through.find_item(r["scene"], mesh, r["frame"])[0]      # kept in the mesh's own space, as it is now
        self.points.append(aim.point(aim.invert(world), hit["point"]))
        self.b.say(f"{len(self.points)} point{'s' if len(self.points) > 1 else ''}  ·  " + HINT)
        self._refresh()

    def bone_at(self, x: float, y: float) -> str:
        """The drawn bone a click at (x, y) device px is on: the nearest within the gizmo's reach (HIT screen px), else ""."""
        if self.mesh or not self._lines or self.v._size is None:
            return ""
        screen = QGuiApplication.primaryScreen()
        reach = HIT * (screen.devicePixelRatio() if screen else 1.0)
        w, h = (n / self.v._scale for n in self.v._size)      # the lines are in parts of the picture; the click in device px
        near = min(((_seg_dist([x, y], [ln["a"][0] * w, ln["a"][1] * h], [ln["b"][0] * w, ln["b"][1] * h]), ln["id"])
                    for ln in self._lines), default=(reach + 1, ""))
        return near[1] if near[0] <= reach else ""

    def _on_selection(self, *_):
        if self.mesh and self.b.selected != self.mesh:
            self.cancel()
        self._refresh()

    def _shown_mesh(self) -> str:
        """The mesh whose chain is drawn: the one being boned, else the selected mesh or bone's, on the Animate page."""
        if self.mesh:
            return self.mesh
        sel = self.b.selected
        if self.b._page != "animate" or not sel or not self.b.doc.has(sel):
            return ""
        while sel and self.b.doc.item(sel).get("type") == "bone":
            sel = self.b.doc.parent_of(sel)[0]
        return sel if sel and self.b.doc.item(sel).get("type") == "mesh" else ""

    def _refresh(self, *_):
        was, self._lines, self._dots = (self._lines, self._dots), [], []
        try:
            self._place(self._shown_mesh())
        except Exception as e:  # noqa: BLE001  no bones drawn when the mesh can't be placed; said, not hidden
            self.b.fail_line(f"Error: bones: {e}")
        if (self._lines, self._dots) != was:          # a scrub step with no bones in sight redraws nothing
            self.changed.emit()

    def _place(self, mesh: str):
        if not mesh or self.v._size is None:
            return
        scene, cam = self.v.sent()
        w, h = self.v._size
        view, frame = View.of(cam, scene, self.b.frame, w, h), self.b.frame
        try:
            world = through.find_item(scene, mesh, frame)[0]
        except ValueError:                                  # not in the picture (hidden, or inside an import): nothing to draw
            return

        def at(p):
            q = view.project(aim.point(world, p))
            return None if q is None else [q[0] / w, q[1] / h]
        chain = skin.bones_of(self.b.doc.item(mesh))
        for m, (bone, _) in zip(skin.transforms(chain, self.b.time, layers.stack_of(self.b.doc.data)), chain):
            s = skin.segment(m, bone)
            a, b = at(s[:3]), at(s[3:])
            if a and b:
                self._lines.append({"a": a, "b": b, "id": bone["id"], "hot": bone["id"] == self.b.selected})
        self._dots = [d for d in (at(p) for p in self.points) if d]
