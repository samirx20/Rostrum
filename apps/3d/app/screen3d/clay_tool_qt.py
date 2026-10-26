"""The Clay tool on screen, for QML as `viewport.clay` (3d-simplicity SPEC § 3, 3d-visual DESIGN § 2, CL1 CONTRACT § 5).
Q (or the rail's Clay button) turns it on; Q again, V or Esc goes back to Select. It is a tool, like Paint: the panel,
the timeline and every other control stay where they are; only the settings panel shows the Clay group (ClayPanel.qml).

What a drag does is one choice of tiles: Make (Lump; Draw and Spin come in CL2) or a Brush (Add, Carve, Smooth; the
rest come later). The brush is the selected clay's `brush` field (the next stroke's settings live on the clay, so an
agent reads and sets them too); Lump is screen state.
- Lump: a click on empty ground or on any other thing makes a new clay there (`clay.add`, the ball the size of the
  brush); a click on a clay joins a ball to it (`clay.lump`). A drag turns the view.
- A brush, a clay selected: a drag on the clay sculpts it (clay_stroke.py), one undo step per stroke; Ctrl held = the
  opposite (Add ↔ Carve), Shift held = Smooth. A drag on empty space turns the view; a click on another thing selects it.
The brush shows as a ring lying on the surface under the pointer (`ring`, parts of the viewport), from a pick per
hover move (newest only); during a stroke it follows the pointer with the shape it had.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from . import clay_ring as R
from .clay_brush_qt import ClayBrush
from .clay_stroke import WORDS, ClayStroke

# The tiles, in panel order: (value, name, one line of what it does). Make, then Brush.
NEW_CLAY = 0.1                  # a new clay's radius (m): hand-sized; its brush starts at a quarter of it (clay.add)
MAKE = [("lump", "Lump", "Click on a clay to join a ball the size of the brush; elsewhere it starts a new clay.")]
BRUSHES = [("add", "Add", "Builds clay up under the brush. Hold Ctrl to carve."),
           ("carve", "Carve", "Takes clay away. Hold Ctrl to add."),
           ("smooth", "Smooth", "Evens bumps out. Hold Shift with any brush to smooth.")]


class ClayTool(ClayStroke, QObject):
    changed = Signal()
    ringChanged = Signal()
    strokeBrushChanged = Signal()
    sculpted = Signal(object)        # (drag number, phase, answer or error line, wall ms, points) from the engine thread
    hovered = Signal(object)         # (hover number, pick answer or error line)
    lumped = Signal(object)          # (pick answer or error line, scene, request) for a Lump click

    def __init__(self, bridge, viewport):
        super().__init__(viewport)
        self.b, self.v = bridge, viewport
        self._on, self._make, self._drag, self._hover, self._hover_busy, self._hover_next = False, "", 0, 0, False, None
        self._ring, self._ring_c = [], None
        self._stroke_reset()
        self.brush = ClayBrush(self)
        self.sculpted.connect(self._on_sculpted)
        self.hovered.connect(self._on_hover)
        self.lumped.connect(self._on_lump)
        bridge.docChanged.connect(self._refresh)
        bridge.selectionChanged.connect(self._refresh)
        bridge.pageChanged.connect(lambda *_: self.leave() if bridge.page != "build" else None)

    # --- what QML reads
    on = Property(bool, lambda s: s._on, notify=changed)
    clayId = Property(str, lambda s: s._clay_id(), notify=changed)
    itemName = Property(str, lambda s: s.b.label_of(s._item()) if s._item() else "", notify=changed)
    tool = Property(str, lambda s: s._tool(), notify=changed)           # "lump" | "add" | "carve" | "smooth"
    make = Property("QVariantList", lambda s: s._tiles(MAKE), notify=changed)
    brushes = Property("QVariantList", lambda s: s._tiles(BRUSHES) if s._item() else [], notify=changed)
    brushObj = Property(QObject, lambda s: s.brush, constant=True)
    # a left drag on the viewport goes to the brush (else it falls through: Lump's click, the view's turn)
    sculpts = Property(bool, lambda s: s._on and s._make == "" and s._item() is not None, notify=changed)
    ring = Property("QVariantList", lambda s: s._ring, notify=ringChanged)
    # the brush the running stroke uses (Ctrl / Shift change it), "" when no stroke runs: the ring's colour says it
    strokeBrush = Property(str, lambda s: s._stroke["brush"] if s._stroke and s._phase in ("wait", "sculpt") else "",
                           notify=strokeBrushChanged)

    def _clay_id(self) -> str:
        sel = self.b.selection
        return sel[0] if len(sel) == 1 and self.b.doc.has(sel[0]) and self.b.doc.item(sel[0]).get("type") == "clay" else ""

    def _item(self):
        cid = self._clay_id()
        return self.b.doc.item(cid) if cid else None

    def _tool(self) -> str:
        it = self._item()
        return self._make or (it.get("brush", "add") if it is not None else "lump")

    def _tiles(self, table):
        now = self._tool()
        return [{"value": v, "label": n, "help": h, "on": v == now} for v, n, h in table]

    def _refresh(self, *_):
        if self._item() is None and self._make == "":
            self._ring = []
            self.ringChanged.emit()
        self.brush.refresh()
        self.changed.emit()

    # --- the tool
    @Slot()
    def toggle(self):
        self.leave() if self._on else self.enter()

    @Slot()
    def enter(self):
        if self.b.page != "build":
            self.b.setPage("build")
        self.v.paint.leave()
        self.v.mesh_edit.leave()
        self.b.add.disarm()
        self._on = True
        self._make = "" if self._item() is not None else "lump"      # nothing to sculpt yet: make one first
        self._refresh()

    @Slot()
    def leave(self):
        if self._on:
            self.cancel()
            self._on, self._ring = False, []
            self.changed.emit()
            self.ringChanged.emit()

    @Slot(str)
    def choose(self, value):
        """A tile: Lump, or a brush (the clay's `brush`, one undo step, as an agent's clay.set)."""
        if value in {v for v, *_ in MAKE}:
            self._make = value
            self._ring = []
            self.ringChanged.emit()
            return self.changed.emit()
        it = self._item()
        if it is None or value not in {v for v, *_ in BRUSHES}:
            return
        self._make = ""
        if it.get("brush") != value:
            self.b._guard(lambda: self.b._apply([{"op": "clay.set", "target": [it["id"]], "args": {"brush": value}}],
                                                f"Brush: {WORDS[value]}"))
        self.changed.emit()

    # --- Lump: the viewport's click (viewport.click asks wants_click first)
    def wants_click(self) -> bool:
        return self._on and self._make == "lump"

    def click(self, x, y):
        scene, req = self.v._pick_at(x, y)

        def job(eng):
            try:
                eng.ensure_scene(scene)
                self.lumped.emit((eng.pick(**req), scene, req))
            except Exception as e:  # noqa: BLE001  said on the status line
                self.lumped.emit((str(e), scene, req))
        self.v._r.call(job)

    def _on_lump(self, answer):
        r, scene, req = answer
        if isinstance(r, str):
            return self.b.fail_line(f"Error: clay: {r}")
        frame = req["frame"]
        clay = r.get("item", "") if r.get("hit") else ""
        size = (self._item() or {}).get("brushSize", 0.03)
        if clay and self.b.doc.has(clay) and self.b.doc.item(clay).get("type") == "clay":
            at = R.to_clay(scene, clay, frame, r["point"])
            size = self.b.doc.item(clay).get("brushSize", size)
            call, label = {"op": "clay.lump", "target": [clay], "args": {"at": at, "radius": size}}, "Lump"
        else:
            point, normal = (r["point"], r["normal"]) if r.get("hit") else self._ground(scene, req)
            if point is None:
                return self.b.fail_line("Error: clay: that click is above the ground and on nothing; click a surface.")
            size = NEW_CLAY                                         # a hand-sized first lump; its brush a quarter of it
            at = [round(p + n * size * 0.8, 4) for p, n in zip(point, normal)]   # sitting on the surface, a little sunk in
            call, label = {"op": "clay.add", "target": [], "args": {"at": at, "radius": size}}, "New clay"
        before = set(self._all_clays())
        if self.b._guard(lambda: self.b._apply([call], label)) and call["op"] == "clay.add":
            new = [c for c in self._all_clays() if c not in before]
            if new:
                self.b.select(new[0])                                # the new clay, ready for the brushes

    def _ground(self, scene, req):
        from . import placing
        from .gizmo import View
        hit = placing.ground_hit(View.of(req, scene, req["frame"], req["width"], req["height"]),
                                 req["x"], req["y"])
        return hit if hit is not None else (None, None)

    def _all_clays(self):
        out, stack = [], list(self.b.doc.data.get("items", []))
        while stack:
            it = stack.pop()
            out += [it["id"]] if it.get("type") == "clay" else []
            stack += it.get("children", [])
        return out

    # --- the ring: a pick per hover move, newest only
    @Slot(float, float, float)
    def hover(self, x, y, dpr):
        if not self.sculpts or self._phase or self.v._size is None:
            return
        self._dpr = dpr
        if self._hover_busy:
            self._hover_next = (x, y)
            return
        self._hover_busy, self._hover = True, self._hover + 1
        scene, req = self.v.sent()
        req = {**req, "x": round(x * dpr * self.v._scale), "y": round(y * dpr * self.v._scale)}
        n = self._hover

        def job(eng):
            try:
                eng.ensure_scene(scene)
                self.hovered.emit((n, eng.pick(**req), scene, req))
            except Exception as e:  # noqa: BLE001
                self.hovered.emit((n, str(e), scene, req))
        self.v._r.call(job)

    @Slot()
    def unhover(self):
        self._hover += 1
        if self._ring and not self._phase:
            self._ring = []
            self.ringChanged.emit()

    def _on_hover(self, answer):
        n, r, scene, req = answer
        self._hover_busy = False
        if n == self._hover and not self._phase and not isinstance(r, str):
            it, ring = self._item(), []
            if it is not None and r.get("hit") and r.get("item") == it["id"]:
                rad = R.world_radius(scene, it["id"], req["frame"], it.get("brushSize", 0.03))
                ring = R.ring(req, scene, req["frame"], r["point"], r["normal"], rad)
            self._ring = ring
            self._ring_c = [req["x"] / req["width"], req["y"] / req["height"]] if ring else None
            self.ringChanged.emit()
        if self._hover_next is not None:
            nxt, self._hover_next = self._hover_next, None
            self.hover(*nxt, self._dpr)

    def _shift_ring(self, x, y):
        """During a stroke the ring keeps its shape and follows the pointer (logical px)."""
        if not self._ring or self._ring_c is None or self.v._size is None:
            return
        w, h = self.v._size
        c = [x * self._dpr * self.v._scale / w, y * self._dpr * self.v._scale / h]
        dx, dy = c[0] - self._ring_c[0], c[1] - self._ring_c[1]
        self._ring, self._ring_c = [[p[0] + dx, p[1] + dy] for p in self._ring], c
        self.ringChanged.emit()
