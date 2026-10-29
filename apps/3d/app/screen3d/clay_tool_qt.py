"""The Clay tool on screen, for QML as `viewport.clay` (3d-simplicity SPEC § 3, 3d-visual DESIGN § 2, CL1 CONTRACT § 5).
Q (or the rail's Clay button) turns it on; Q again, V or Esc goes back to Select; so does a shape picked from the rail
(Box, Ball, …: the next press places it). It is a tool, like Paint: the panel,
the timeline and every other control stay where they are; only the settings panel shows the Clay group (ClayPanel.qml).

What a drag does is one choice of tiles: Make (Draw, chosen when the tool turns on; Spin; Lump) or a Brush (the six
that shape: Add, Carve, Smooth, Pull, Flatten, Crease; then Mask, which protects). The brush is the selected clay's
`brush` field (the next stroke's settings live on the clay, so an agent reads and sets them too); Make is screen state.
- Draw, Spin: a left drag draws an outline (or half a profile) that puffs (or spins) into clay (clay_draw_qt.py,
  `drawer`); it never turns the view.
- Turn into clay: a tile shown only while an exact part or import is selected; one `clay.from_item`, the new clay
  selected (the same as its right-click entry, actions3d.py).
- Lump: a click on empty ground or on any other thing makes a new clay there (`clay.add`, the ball the size of the
  brush); a click on a clay joins a ball to it (`clay.lump`). A drag turns the view.
- A brush, a clay selected: a drag on the clay sculpts it (clay_stroke.py), one undo step per stroke; Ctrl held = the
  opposite (Add ↔ Carve; Flatten puffs out, Crease pinches to a ridge, Mask unmasks: `invert`), Shift held = Smooth.
  A pen's pressure goes with each point. A drag on empty space turns the view; a click on another thing selects it.
- F held (the key map's clay_size, a hold key) and the pointer moved left or right: the ring under the pointer grows or
  shrinks live, with its size beside it (`sizeText`); letting F go is one `clay.set` of brushSize (one undo step).
The brush shows as a ring lying on the surface under the pointer (`ring`, parts of the viewport), tilted with it, from a
pick per hover move (newest only); during a stroke it follows the pointer with the shape it had. A faint inner circle
is where the brush works at half strength (`ringInner`, from Falloff); Ctrl held shows what the opposite does in the
middle ("−" takes away, "+" adds: `ringMark`) the moment the key goes down. While a drag off the clay turns the view,
`orbiting` is true (the pointer shows the turn).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QEvent, QObject, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication, QKeySequence
from rostrum3d import fields as F
from rostrum3d.clay_fields import SOURCES
from rostrum_gui.gui_filter import GuiFilter

from . import clay_ring as R
from .clay_brush_qt import ClayBrush
from .clay_layers_qt import ClayLayers
from .clay_steps_qt import ClaySteps
from .clay_draw_qt import ClayDraw
from .clay_stroke import WORDS, ClayStroke

# The tiles, in panel order: (value, name, one line of what it does). Make, then Brush (the six that shape), then Mask.
NEW_CLAY = 0.1                  # a new clay's radius (m): hand-sized; its brush starts at a quarter of it (clay.add)
MAKE = [("draw", "Draw", "Drag an outline: it puffs into clay. Started on a clay, it joins it."),
        ("spin", "Spin", "Drag half a profile from the line at the pointer: it spins into a round shape."),
        ("lump", "Lump", "Click on a clay to join a ball the size of the brush; elsewhere it starts a new clay.")]
TURN = ("turn", "Turn into clay", "A clay copy of the selected part to sculpt; the part is hidden, not deleted.")
TURNS = SOURCES                            # what Turn into clay takes: exact parts (shapes, combines, an import's parts), imports
BRUSHES = [("add", "Add", "Builds clay up under the brush. Hold Ctrl to carve."),
           ("carve", "Carve", "Takes clay away. Hold Ctrl to add."),
           ("smooth", "Smooth", "Evens bumps out. Hold Shift with any brush to smooth."),
           ("pull", "Pull", "Grabs the clay under the brush and drags it along: a nose, a chin, an ear tip."),
           ("flatten", "Flatten", "Planes the clay towards its average surface. Hold Ctrl to puff it out."),
           ("crease", "Crease", "Pinches a sharp line or valley: lips, eyelids, folds. Hold Ctrl for a ridge.")]
MASKS = [("mask", "Mask", "Paints a mask: no brush changes masked clay. Hold Ctrl to take the mask away.")]
SIZE_KEY = "clay_size"          # keys3d.py: F, a hold key this tool watches itself (KeyMap skips it, so no shortcut eats it)


def _mm(size: float) -> str:
    """A brush size (m) as the F drag's chip says it: millimetres below a metre."""
    if size >= 1:
        return f"{size:.2f} m"
    return f"{size * 1000:.1f} mm" if size < 0.01 else f"{size * 1000:.0f} mm"


class SizeKey(GuiFilter):
    """F down and up for the size drag, while Clay is on, from the window's own key events (a shortcut sees no release).
    A text box that has the keys keeps its F."""

    def __init__(self, tool):
        super().__init__(tool)
        self.t = tool

    def _ours(self, event, plain=True) -> bool:
        """F (or the person's own key for it); `plain`: with no Ctrl / Shift / Alt (Shift+F is Look). Its release counts
        whatever is held then."""
        if plain and event.modifiers() not in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.KeypadModifier):
            return False
        km = getattr(getattr(getattr(self.t.b, "actions", None), "list", None), "keymap", None)
        if km is None:
            from .keys3d import KEYS3D as km
        return SIZE_KEY in km.held(QKeySequence(event.key()).toString())

    def on_event(self, obj, event) -> bool:
        kind = event.type()
        if kind not in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease) or not self.t._on:
            return False
        self._held(event)
        if kind == QEvent.Type.KeyRelease:
            if self.t._sizing and not event.isAutoRepeat() and self._ours(event, plain=False):
                self.t.sizeEnd()
                return True
            return False
        focus = QGuiApplication.focusObject()
        if focus is not None and (focus.inherits("QQuickTextInput") or focus.inherits("QQuickTextEdit")):
            return False
        if event.isAutoRepeat():
            return self.t._sizing and self._ours(event, plain=False)     # F still held: its repeats are swallowed
        return self._ours(event) and self.t.sizeBegin()

    def _held(self, event):
        """Ctrl or Shift down or up: the ring's mark at once, not on the next pointer move. The key itself says whether
        it is down (its event's modifiers don't always count it); the other one comes from the modifiers. Never taken:
        the key goes on as it would."""
        key, m = event.key(), event.modifiers()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift):
            down = event.type() == QEvent.Type.KeyPress
            self.t.held(down if key == Qt.Key.Key_Control else bool(m & Qt.KeyboardModifier.ControlModifier),
                        down if key == Qt.Key.Key_Shift else bool(m & Qt.KeyboardModifier.ShiftModifier))


class ClayTool(ClayStroke, QObject):
    changed = Signal()
    ringChanged = Signal()
    ringShiftChanged = Signal()
    strokeBrushChanged = Signal()
    sculpted = Signal(object)        # (drag number, phase, answer or error line, wall ms, points) from the engine thread
    hovered = Signal(object)         # (hover number, pick answer or error line)
    lumped = Signal(object)          # (pick answer or error line, scene, request) for a Lump click
    sizingChanged = Signal()
    markChanged = Signal()

    def __init__(self, bridge, viewport):
        super().__init__(viewport)
        self.b, self.v = bridge, viewport
        self._on, self._make, self._drag, self._hover, self._hover_busy, self._hover_next = False, "", 0, 0, False, None
        self._ring, self._ring_c, self._hit = [], None, None      # _hit: the last hover's (req, scene, point, normal)
        self._shift = [0.0, 0.0]                                    # how far the ring slid since it was laid (a stroke)
        self.ringChanged.connect(self._unshift)
        self._sizing, self._size0, self._ring0, self._size_x, self._size_now = False, 0.0, 0.0, None, 0.0
        self._ringer, self._ctrl, self._shift = R.Ringer(), False, False
        self._keys = SizeKey(self)
        self._stroke_reset()
        self.brush = ClayBrush(self)
        self.drawer = ClayDraw(self)
        self.steps = ClaySteps(self)                                         # the Steps list and Puff (ClaySteps.qml)
        self.layers = ClayLayers(self)                                       # sculpt layers (ClayLayers.qml)
        self.sculpted.connect(self._on_sculpted)
        self.hovered.connect(self._on_hover)
        self.lumped.connect(self._on_lump)
        self.changed.connect(self.markChanged)
        self.strokeBrushChanged.connect(self.markChanged)
        bridge.docChanged.connect(self._refresh)
        bridge.selectionChanged.connect(self._refresh)
        bridge.pageChanged.connect(lambda *_: self.leave() if bridge.page != "build" else None)
        # a shape picked from the rail (Box, Ball, …) leaves Clay: the next press places it, not a Draw or a stroke
        bridge.add.armedChanged.connect(lambda: self.leave() if bridge.add.armed else None)

    # --- what QML reads
    on = Property(bool, lambda s: s._on, notify=changed)
    clayId = Property(str, lambda s: s._clay_id(), notify=changed)
    itemName = Property(str, lambda s: s.b.label_of(s._item()) if s._item() else "", notify=changed)
    tool = Property(str, lambda s: s._tool(), notify=changed)           # "draw" | "spin" | "lump" | a brush
    make = Property("QVariantList", lambda s: s._tiles(MAKE) + s._turn_tile(), notify=changed)
    brushes = Property("QVariantList", lambda s: s._tiles(BRUSHES) if s._item() else [], notify=changed)
    masks = Property("QVariantList", lambda s: s._tiles(MASKS) if s._item() else [], notify=changed)
    # F held: the pointer's moves size the brush (ClayStrokes sends them to sizeMove) and no stroke starts
    sizing = Property(bool, lambda s: s._sizing, notify=sizingChanged)
    brushObj = Property(QObject, lambda s: s.brush, constant=True)
    drawObj = Property(QObject, lambda s: s.drawer, constant=True)        # Draw and Spin (ClayDraw.qml)
    stepsObj = Property(QObject, lambda s: s.steps, constant=True)        # Steps list, Puff (ClaySteps.qml)
    layersObj = Property(QObject, lambda s: s.layers, constant=True)      # sculpt layers (ClayLayers.qml)
    # a left drag on the viewport draws (Draw, Spin): never turns the view
    draws = Property(bool, lambda s: s._on and s._make in ("draw", "spin"), notify=changed)
    # a left drag on the viewport goes to the brush (else it falls through: Lump's click, the view's turn)
    sculpts = Property(bool, lambda s: s._on and s._make == "" and s._item() is not None, notify=changed)
    ring = Property("QVariantList", lambda s: s._ring, notify=ringChanged)
    # during a stroke the ring keeps its shape and slides with the pointer: a move of the drawn ring (a share of the
    # viewport), not a new outline to lay out at every pointer move (3d-v3: that cost the window ~3 ms a dab)
    ringShift = Property("QVariantList", lambda s: s._shift, notify=ringShiftChanged)
    # the brush the running stroke uses (Ctrl / Shift change it), "" when no stroke runs
    strokeBrush = Property(str, lambda s: s._stroke["brush"] if s._stroke and s._phase in ("wait", "sculpt") else "",
                           notify=strokeBrushChanged)
    # a drag off the clay turning the view (the pointer shows it while the drag lasts)
    orbiting = Property(bool, lambda s: s._phase == "orbit", notify=strokeBrushChanged)
    # the ring's faint inner circle (where the brush works at half strength), a share of its radius; its mark ("−", "+")
    ringInner = Property(float, lambda s: R.inner(s._looks()[1]), notify=markChanged)
    ringMark = Property(str, lambda s: s._looks()[0], notify=markChanged)
    # F + drag: the size the ring shows now ("30 mm"), "" when not sizing
    sizeText = Property(str, lambda s: _mm(s._size_now) if s._sizing else "", notify=ringChanged)

    def _clay_id(self) -> str:
        sel = self.b.selection
        return sel[0] if len(sel) == 1 and self.b.doc.has(sel[0]) and self.b.doc.item(sel[0]).get("type") == "clay" else ""

    def _item(self):
        cid = self._clay_id()
        return self.b.doc.item(cid) if cid else None

    def _tool(self) -> str:
        it = self._item()
        return self._make or (it.get("brush", "add") if it is not None else "lump")

    def _looks(self) -> tuple[str, float]:
        """(the ring's mark, its falloff): the running stroke's (Ctrl at its press), else what a press now would do."""
        it = self._item()
        if it is None:
            return "", 0.5
        if self._stroke is not None and self._phase in ("wait", "sculpt"):
            s = self._stroke
            return R.mark_of(it.get("brush", "add"), s["brush"], s["invert"]), s["falloff"]
        return R.mark(it.get("brush", "add"), self._ctrl, self._shift), it.get("brushFalloff", 0.5)

    @Slot(bool, bool)
    def held(self, ctrl, shift):
        """Ctrl / Shift as they are now (the window's key events, and every pointer move's)."""
        if (ctrl, shift) != (self._ctrl, self._shift):
            self._ctrl, self._shift = ctrl, shift
            self.markChanged.emit()

    def _tiles(self, table):
        now = self._tool()
        return [{"value": v, "label": n, "help": h, "on": v == now} for v, n, h in table]

    def _turnable(self) -> list[str]:
        doc = self.b.doc
        return [i for i in self.b.selection if doc.has(i) and doc.item(i).get("type") in TURNS]

    def _turn_tile(self):
        return [{"value": TURN[0], "label": TURN[1], "help": TURN[2], "on": False}] if self._turnable() else []

    @Slot()
    def turnIntoClay(self):
        """The selected exact parts and imports, each a clay copy (the originals hidden): one change; the new clay
        selected, ready for the brushes."""
        ids = self._turnable()
        if not ids:
            return
        before = set(self._all_clays())
        label = f"Turn {self.b.label_of(self.b.doc.item(ids[0]))} into clay" if len(ids) == 1 else "Turn into clay"
        if self.b._guard(lambda: self.b._apply([{"op": "clay.from_item", "target": ids, "args": {}}], label)):
            new = [c for c in self._all_clays() if c not in before]
            if new:
                self.b.select(new[0])

    def _refresh(self, *_):
        if self._item() is None and self._make == "":
            self._ring = []
            self.ringChanged.emit()
        self.brush.refresh()
        self.changed.emit()

    # --- the tool
    def _rows_again(self):
        """The settings panel's rows read `sculpting` (the tool being on): a clay's Brush group comes and goes with it."""
        self.b.model.update(self.b._rows())

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
        self._keys.watch_windows(QGuiApplication.instance())     # F for the size drag (each window once)
        self._make = "draw"                                          # SPEC § 1 0:00: Draw is chosen
        self._rows_again()
        self._refresh()
        self.v.redraw()                                  # the sculpted clay's outline goes (sculpting())

    @Slot()
    def leave(self):
        if self._on:
            self.sizeCancel()
            self.cancel()
            self.drawer.cancel()
            self.drawer.unhover()
            self._on, self._ring = False, []
            self._rows_again()
            self.changed.emit()
            self.ringChanged.emit()
            self.v.redraw()                                  # its outline back (sculpting(): none while Clay is on)

    def sculpting(self, item_id: str) -> bool:
        """Clay is on with this clay to sculpt: the viewport draws no outline on it (the brush ring is its mark)."""
        return self._on and bool(item_id) and item_id == self.clayId

    @Slot(str)
    def choose(self, value):
        """A tile: Draw, Spin, Lump, Turn into clay, or a brush (the clay's `brush`, one undo step, as an agent's
        clay.set)."""
        if value == TURN[0]:
            return self.turnIntoClay()
        if value in {v for v, *_ in MAKE}:
            self.drawer.unhover()
            self._make = value
            self._ring = []
            self.ringChanged.emit()
            return self.changed.emit()
        it = self._item()
        if it is None or value not in {v for v, *_ in BRUSHES + MASKS}:
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
        if not self.sculpts or self._phase or self._sizing or self.v._size is None:
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
        if self._ring and not self._phase and not self._sizing:
            self._ring = []
            self.ringChanged.emit()

    def _on_hover(self, answer):
        n, r, scene, req = answer
        self._hover_busy = False
        if n == self._hover and not self._phase and not self._sizing and not isinstance(r, str):
            it, ring = self._item(), []
            if it is not None and r.get("hit") and r.get("item") == it["id"]:
                ring = self._ringer.ring(req, scene, req["frame"], r["point"], r["normal"], it["id"],
                                         it.get("brushSize", 0.03))
                self._hit = (req, scene, r["point"], r["normal"])
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
        self._shift = [c[0] - self._ring_c[0], c[1] - self._ring_c[1]]
        self.ringShiftChanged.emit()

    def _unshift(self):
        """A ring laid anew (a hover, F's size, none): it sits where it was laid."""
        if self._shift != [0.0, 0.0]:
            self._shift = [0.0, 0.0]
            self.ringShiftChanged.emit()

    # --- F + drag: the brush size (the ring is the only thing drawn; one clay.set when F comes up)
    def sizeBegin(self) -> bool:
        """F went down: taken (True) while a clay is sculpted. It sizes the ring on the clay under the pointer; with no
        ring there the status line says where to point."""
        it = self._item()
        if self._sizing or not self.sculpts or self._phase or it is None or self.v._size is None:
            return self._sizing
        if not self._ring or self._hit is None:
            self.b.say("Size: rest the pointer on the clay, then hold F and move left or right")
            return True
        w, h = self.v._size
        self._sizing, self._size0, self._size_x = True, float(it.get("brushSize", 0.03)), None
        self._size_now = self._size0
        self._ring0 = R.ring_px(self._ring, self._ring_c, w, h) / (self._dpr * self.v._scale)    # logical px
        self.sizingChanged.emit()
        return True

    @Slot(float, float)
    def sizeMove(self, x, y):
        """The pointer moved with F held (logical px): the first move is the start; to the right the ring grows."""
        if not self._sizing:
            return
        if self._size_x is None:
            self._size_x = x
            return
        p, it = F.param("clay", "brushSize"), self._item()
        if it is None:
            return self.sizeCancel()
        self._size_now = R.sized(self._size0, self._ring0, x - self._size_x, p.min, p.max)
        req, scene, point, normal = self._hit
        self._ring = self._ringer.ring(req, scene, req["frame"], point, normal, it["id"], self._size_now) or self._ring
        self.ringChanged.emit()

    @Slot()
    def sizeEnd(self):
        """F came up: one clay.set of the new size (one undo step); nothing when it did not change."""
        if not self._sizing:
            return
        self._sizing, it, size = False, self._item(), self._size_now
        self.sizingChanged.emit()
        if it is not None and abs(size - self._size0) > 1e-9:
            self.b._guard(lambda: self.b._apply([{"op": "clay.set", "target": [it["id"]], "args": {"brushSize": size}}],
                                                f"Brush size on {self.b.label_of(it)}"))

    def sizeCancel(self):
        """Left with F still down (the tool left, the clay gone): the size stays as it was."""
        if self._sizing:
            self._sizing = False
            self.sizingChanged.emit()
