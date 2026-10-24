"""Edit mesh on screen, for QML as `meshEdit` (SPEC §4.3, §14): Tab enters and leaves on the selected mesh or combine
(one that isn't an editable mesh yet first offers "Turns the box into an editable mesh · Edit": `mesh.edit`, one undo
step); 1 / 2 / 3 pick points / edges / faces; a click picks what is under the pointer (Shift adds or takes away), a
drag on empty space draws a box. The selection is screen state; operations get it as selector text (mesh_edit.py).
The panel's actions and the extrude arrow are mesh_actions.py's; the gizmo on the selection is gizmo_qt.py's.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication
from rostrum3d import aim, fields as F, through

from . import gizmo as G, mesh_edit as M
from .mesh_actions import MeshActions

SHAPE_WORDS = {"box": "box", "sphere": "sphere", "cylinder": "cylinder", "cone": "cone", "capsule": "capsule",
               "torus": "torus", "plane": "plane", "text": "text", "logo": "logo", "drawing": "drawing"}


class MeshEdit(MeshActions, QObject):
    changed = Signal()

    def __init__(self, bridge, viewport):
        QObject.__init__(self, viewport)
        self.bridge, self.vp = bridge, viewport
        self._on, self._kind, self._sel, self._geo, self._id = False, "faces", set(), None, ""
        self._init_actions()
        viewport.serialChanged.connect(self._refresh)
        bridge.docChanged.connect(self._refresh)
        bridge.selectionChanged.connect(self._on_selection)

    on = Property(bool, lambda s: s._on, notify=changed)
    kind = Property(str, lambda s: s._kind, notify=changed)
    count = Property(str, lambda s: M.label(s._kind, len(s._sel)), notify=changed)
    picked = Property(int, lambda s: len(s._sel), notify=changed)
    needsEdit = Property(bool, lambda s: s._on and s._poly() is None, notify=changed)
    shapeWord = Property(str, lambda s: s._shape_word(), notify=changed)
    actions = Property("QVariantList", lambda s: s._actions(), notify=changed)    # what fits the selection type
    lastAction = Property(str, lambda s: s._last_word(), notify=changed)
    numbers = Property("QVariantList", lambda s: s._numbers(), notify=changed)   # the last action's, in mm
    dragLabel = Property(str, lambda s: s._drag_label(), notify=changed)
    overlay = Property("QVariantMap", lambda s: s._overlay(), notify=changed)    # in parts of the viewport (0..1)

    # --- the item edited
    def _item(self):
        sel = self.bridge.selected
        if not sel or not self.bridge.doc.has(sel) or len(self.bridge.selection) > 1:
            return None
        it = self.bridge.doc.item(sel)
        return it if it["type"] in F.SOLIDS else None

    def _poly(self):
        it = self._item()
        return it if it is not None and it["type"] == "mesh" and it.get("shape") == "poly" and it.get("points") else None

    def _shape_word(self):
        it = self._item()
        return "" if it is None else "combine" if it["type"] == "combine" else SHAPE_WORDS.get(it.get("shape"), "shape")

    def px(self) -> float:
        screen = QGuiApplication.primaryScreen()
        return self.vp._scale * (screen.devicePixelRatio() if screen else 1.0)

    def _refresh(self, *_):
        self._geo = None
        it = self._poly() if self._on else None
        if it is not None and self.vp._size is not None:
            try:
                scene, cam = self.vp.sent()
                w, h = self.vp._size
                world = through.find_item(scene, it["id"], self.bridge.frame)[0]
                self._geo = M.Geo(it, world, G.View.of(cam, scene, self.bridge.frame, w, h))
            except Exception as e:  # noqa: BLE001  said, not hidden
                self.bridge.fail_line(f"Error: edit mesh: {e}")
        if self._geo is not None:
            self._sel = {i for i in self._sel if i < self._geo.count(self._kind)}
        self.changed.emit()

    def _on_selection(self, *_):
        if self._on and (self._item() is None or self.bridge.selected != self._id):
            self.leave()

    # --- the mode
    @Slot()
    def toggle(self):
        self.leave() if self._on else self.enter()

    @Slot()
    def enter(self):
        it = self._item()
        if it is None:
            return self.bridge.fail_line("Edit mesh needs one shape or combine selected.")
        self._on, self._id, self._sel = True, it["id"], set()
        self._last = None
        self._refresh()

    @Slot()
    def leave(self):
        if self._on:
            self._on, self._sel, self._geo, self._last = False, set(), None, None
            self.changed.emit()

    @Slot()
    def convert(self):
        """Edit: the shape or combine becomes an editable mesh (`mesh.edit`, one undo step)."""
        it = self._item()
        if it is not None:
            self.bridge._guard(lambda: self.bridge._apply([{"op": "mesh.edit", "target": [it["id"]], "args": {}}],
                                                           f"Edit mesh {self.bridge.label_of(it)}"))
            self._refresh()

    @Slot(str)
    def setKind(self, kind):
        if kind in M.KINDS and kind != self._kind:
            self._kind, self._sel, self._last = kind, set(), None
            self.changed.emit()

    # --- picking (positions in parts of the viewport, 0..1)
    def _pt(self, fx, fy):
        w, h = self.vp._size
        return fx * w, fy * h

    @Slot(float, float, bool)
    def clickAt(self, fx, fy, shift):
        if self._geo is None:
            return
        hit = M.pick(self._geo, self._kind, *self._pt(fx, fy), self.px())
        if hit is None:
            new = self._sel if shift else set()
        else:
            new = (self._sel ^ {hit}) if shift else {hit}
        self._set_sel(new)

    @Slot(float, float, float, float, bool)
    def boxSelect(self, fx0, fy0, fx1, fy1, shift):
        if self._geo is None:
            return
        got = M.boxed(self._geo, self._kind, [*self._pt(fx0, fy0), *self._pt(fx1, fy1)])
        self._set_sel(self._sel | got if shift else got)

    def select_text(self, text):
        """The selection from selector text (scripted steps; the same words agents use): "top", "faces 3", "all"."""
        from rostrum3d import mesh_select
        kind, got = mesh_select.parse(text, self._poly())
        if kind == "edges":
            got = {self._geo.edges.index(e) for e in got}
        self._kind = kind
        self._set_sel(set(got))

    def _set_sel(self, new):
        if new != self._sel:
            self._sel, self._last = set(new), None
        self.changed.emit()

    def selector(self) -> str:
        return M.selector(self._kind, M.as_items(self._geo, self._kind, self._sel))

    # --- what the gizmo stands on in edit mode
    def gizmo_frame(self):
        """{origin, own} for the gizmo: the selection's centre and the item's own axes in the world; None without one."""
        if not self._on or self._geo is None or not self._sel or self.arrow_shown():
            return None
        return {"origin": M.centre(self._geo, self._kind, self._sel), "own": G.columns(self._geo.world[0])}

    def gizmo_call(self, kind, axis, amount):
        """One drag step of the gizmo as a `mesh.transform` call in the item's own space: move (a world vector), turn
        (degrees around own axis `axis`), scale (a factor along own axis `axis`)."""
        a = {"select": self.selector()}
        if kind == "move":
            a["move"] = [round(x, 7) for x in aim._apply(aim._inverse(self._geo.world[0]), amount)]
        elif kind == "turn":
            a["turn"] = [round(amount, 5) if i == axis else 0.0 for i in range(3)]
        else:
            a["scale"] = [round(amount, 6) if i == axis else 1.0 for i in range(3)]
        return {"op": "mesh.transform", "target": [self._id], "args": a}

    def _overlay(self):
        if self._geo is None:
            return {}
        w, h = self.vp._size
        o = M.overlay(self._geo, self._kind, self._sel)
        fr = lambda p: [p[0] / w, p[1] / h]          # noqa: E731
        out = {k: [[fr(p) for p in seg] for seg in v] if k in ("lines", "edges", "faces") else [fr(p) for p in v]
               for k, v in o.items()}
        arr = self.arrow_now()
        out["arrow"] = [fr(arr[0]), fr(arr[1])] if arr else []
        return out
