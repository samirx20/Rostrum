"""The Draw tool's side of the screen: the pen, the brush, drawings frame by frame, the onion skin.

Every change is an operation recorded through the document (a stroke = one gesture; "new drawing" and "hold" =
one `doc.apply` each). The brush and the onion toggle are screen state. The brush panel is the kit's Inspector
on this object (brush_panel.py), so the panel is built from the brush settings' own rules, not by hand.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from rostrum2d.drawing import each_frame, frame_at, frame_number
from rostrum2d.names import display_name
from rostrum2d import paint_overflow
from rostrum2d.ops_paint import PAINTABLE
from rostrum_gui import rows
from rostrum_gui.after_frame import AfterFrame
from rostrum_gui.frames import ImageProvider
from rostrum_gui.model import RowsModel
from rostrum_gui.select_soon import SelectSoon

from rostrum2d import painted_fill, paintings

from . import adding, brush_presets, fill_aim, framing, onion, wet_through, wet_uses, wet_wrap
from .wet import WetView, reveal_rect, smear_ink, without_paint
from .pen_tilt import PenTilt
from .brush import Brush
from .brush_panel import BrushPanel
from .strokes import StrokeDrag, check_showing


class Painter(BrushPanel):
    # What QML reads, in three groups, each told only when one of its values changed (_refresh): one signal for all
    # of them re-ran every painter binding of the window (the Layer ▾ list, the onion rows, the brush header) at each
    # new drawing and each frame of a scrub.
    framesChanged = Signal()        # the drawing at the playhead
    onionChanged = Signal()         # the onion skin
    targetChanged = Signal()        # what the pen paints on
    _GROUPS = (("framesChanged", ("drawingId", "now", "newHold")),
               ("onionChanged", ("onionOn", "onionReach", "onionSerial", "onionHere")),
               ("targetChanged", ("targetName", "targetValue", "targetChoices", "canErase", "canNewLayer", "newLayerNext")))
    _revealed = Signal(object, object, object)     # the eraser's ink, the frame without its layer, an error (worker thread)

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._stroke, self._onion = bridge, None, False
        self._fresh, self._new_layer = None, False      # "New drawing" picked for this selection; next stroke: new paint layer
        self._target = None                             # (document state, layer, what the pen paints on): target()
        self._on_fill = {}                              # element id -> B paints its painted fill (True) or own paint (fill_aim)
        self._showing = False                           # a stroke's picture is asked for (strokeTo)
        self.brush = Brush(bridge.comp().get("background", ""))
        self.tilt = PenTilt(self)                       # the pen's lean (Session.show watches the window with it)
        self.brush.tilt_pen = self.tilt.has_tilt
        self.tilt.changed.connect(self._tilt_pen)
        self._serial, self._built, self._rev = 0, None, 0        # _rev: the document changed (the onion is stale)
        self._reach = {"before": 2, "after": 1}         # onion skin: how many drawings each way (screen state)
        self.provider = ImageProvider()                  # image://onion: the newest onion picture
        self._wet = WetView(bridge.frameChanged, self)     # the stroke being drawn, shown at once (wet.py)
        self._select_made = SelectSoon(bridge, self)        # the drawing a first stroke made: picked the frame after
        bridge.opened.landed.connect(self._wet.landed)     # ... on a painting opened on its own, until its picture lands
        self._revealed.connect(self._reveal)
        self.previews = brush_presets.PreviewProvider()     # image://brushes: the shipped ones and My brushes
        self._mine = []                                 # My brushes: the project's saved brushes (brush_panel.py)
        self._told = [None] * len(self._GROUPS)         # what QML last heard of each group (_refresh)
        self._soon = AfterFrame(self._refresh, self)    # _refresh the frame after (the playhead moved)
        self.ahead = None                               # the eraser's reveal drawn ahead (reveal_ahead.py; the bridge's)
        self.model = RowsModel(rows.ROLES, self)
        self.model.reset(self.brush.rows(bool(self.b.doc.folder)))
        self.refreshBrushes()
        bridge.docChanged.connect(self._doc_changed)
        bridge.docStepped.connect(self._doc_changed)       # a drag's step moves what the onion shows too
        bridge.outlineChanged.connect(self._refresh)
        bridge.timeChanged.connect(self._soon.ask)         # the navigator and the onion follow the playhead, the frame
                                                        # after its own (a new drawing's frame tools showing: ~13 ms)
        self.targetChanged.connect(self.headerChanged)  # the header names what the pen paints on (not brushChanged: a
                                                        # pick re-ran the brush list, the paint tool and its rows)
        self.brushChanged.connect(self.headerChanged)   # ... and the brush being edited

    # ---- reads for QML ----------------------------------------------------------------------------------------
    def target(self) -> dict | None:
        """The selected layer the pen paints on: a drawing, or any element that can hold paint (ops_paint.PAINTABLE)."""
        opened = self.b.opened.item()
        if opened is not None:                  # a painting open on its own (painting_open.py): the pen paints on it
            return opened
        layer, data, got = self.b.selectedLayer, self.b.doc.data, self._target
        if got is None or got[0] is not data or got[1] != layer:     # once per document state (never changed in place)
            item = self.b.doc.item(layer) if layer else None
            got = self._target = (data, layer, item if item and item["type"] in PAINTABLE else None)
        return got[2]

    def drawing(self) -> dict | None:
        """What the frame tools work on: the selected drawing, an element holding paint, a painting opened on its own,
        or, painting a painted fill in place, its painting (the drawing that layer shows at the playhead)."""
        t, aim = self.target(), self._aim()
        item = aim if aim is not None and aim is not t else t
        return item if item and (item["type"] == "drawing" or item.get("frames")) else None

    onionHere = Property(bool, lambda self: self.through() is None, notify=onionChanged)   # the onion skin lies over the layer's box

    def _cells(self) -> dict | None:
        """The drawing whose cells the timeline shows (and the onion skin, over its box): not a painting painted in
        place (its drawings run through that layer's start, phase and loop, not the layer's row)."""
        return None if self.through() is not None else self.drawing()

    def _n(self) -> int:
        """The frame the pen paints at, in what it paints on: the selected layer's own frame, or, painting its painted
        fill, the painting's drawing that layer shows now."""
        if self.b.opened.on:
            return self.b.opened.frame()
        n = frame_number(self.b.own_t(self.b.selectedLayer), self.b.comp()["fps"])
        through = self.through()
        if through is None:
            return n
        shown = painted_fill.shown(through, self._aim(), n, self.b.comp()["fps"])
        return shown["at"] if shown else 0

    def through(self) -> dict | None:
        """The element the pen paints through into its painted fill (painting in place), else None."""
        t, d = self.target(), self._aim()
        return t if t is not None and d is not None and d is not t else None

    @Property(str, notify=framesChanged)
    def drawingId(self):
        """The selected frame-by-frame layer (Draw each frame on): only it shows the timeline's frame tools (UX_SPEC
        3.9). Alt+N works on any painted element (it turns Draw each frame on): it reads drawing(), not this."""
        d = self._cells()
        return d["id"] if d and each_frame(d) else ""

    @Property("QVariantMap", notify=framesChanged)
    def now(self):
        """Which drawing buttons apply at the playhead (see framing.state); {} with no drawing selected."""
        d = self.drawing()
        return framing.state(d, self._n()) if d else {}

    onionOn = Property(bool, lambda self: self._onion, notify=onionChanged)
    onionReach = Property("QVariantMap", lambda self: dict(self._reach), notify=onionChanged)

    @Property(int, notify=framesChanged)
    def newHold(self):
        d = self.drawing()
        return int(d.get("newHold") or 2) if d else 2

    @Property(int, notify=onionChanged)
    def onionSerial(self):
        return self._serial if self._onion and self._built else 0

    # ---- what the pen paints on (PaintTarget.qml: "Painting on · Layer ▾") ---------------------------------------
    def _aim(self) -> dict | None:
        """What the pen paints on: the target, or the painting it is filled with (fill_aim.on_fill); None when "New
        drawing" was picked for this selection."""
        if self._fresh == self.b.selectedLayer and self._fresh is not None and not self.b.opened.on:
            return None
        t = self.target()
        p = fill_aim.painting_of(self.b.doc, t)
        return p if p is not None and fill_aim.on_fill(t, self._on_fill) else t

    @Property(str, notify=targetChanged)
    def targetName(self):
        d = self._aim()
        return display_name(d) if d else "New drawing"

    @Property(str, notify=targetChanged)
    def targetValue(self):
        """Which of targetChoices is on: "selected" or "new"; on an element with a painted fill "own" or "fill"."""
        d = self._aim()
        if d is not None and fill_aim.painting_of(self.b.doc, self.target()) is not None:
            return fill_aim.FILL if self.through() is not None else fill_aim.OWN
        return "selected" if d else "new"

    @Property("QVariantList", notify=targetChanged)
    def targetChoices(self):
        """Painting on › Layer ▾: the selected layer (an element with a painted fill: its own paint and the painting),
        the other painted layers (newest first), New drawing."""
        d = self.target()
        if self.b.opened.on:                     # only the painting: Layer ▾ is not shown then (PaintTarget.qml)
            return [{"value": "selected", "label": display_name(d)}]
        fill = fill_aim.painting_of(self.b.doc, d)
        painted = [it for it in reversed(list(self.b.doc.items())) if it["type"] in PAINTABLE and it["type"] != "painting"
                   and (it["type"] == "drawing" or it.get("frames")) and (not d or it["id"] != d["id"])]     # (a painting is no layer)
        return (fill_aim.choices(d, fill) if fill else [{"value": "selected", "label": display_name(d)}] if d else []) +             [{"value": it["id"], "label": display_name(it)} for it in painted] + [{"value": "new", "label": "New drawing"}]

    @Slot(str)
    def paintOn(self, which):
        """"new": the next stroke makes a new drawing (for this selection); "selected": back to the selected layer;
        "own" / "fill": the selected element's own paint or its painted fill; another layer's id: it is selected, so
        the pen paints on it."""
        if which in (fill_aim.OWN, fill_aim.FILL):
            self._fresh = None
            self._on_fill[self.b.selectedLayer] = which == fill_aim.FILL
        elif which not in ("new", "selected"):
            self._fresh = None
            self.b.select(which)
        else:
            self._fresh = self.b.selectedLayer if which == "new" else None
        self._refresh()

    @Slot()
    def paintFill(self):
        """The fill picker's Paint it: the Brush on, painting the selected element's painted fill."""
        if fill_aim.painting_of(self.b.doc, self.target()) is not None:
            self.paintOn(fill_aim.FILL)
            self.b.paintTool.use("brush")

    def _erasing(self) -> bool:
        return self.brush.values.get("mode") == "erase"

    @Property(bool, notify=targetChanged)
    def canErase(self):
        """The eraser has paint to take away: what the pen paints on holds some (else the pointer says it can't)."""
        d = self._aim()
        return bool(d and (d["type"] == "drawing" or d.get("frames")))

    @Property(bool, notify=targetChanged)
    def canNewLayer(self):
        d = self._aim()
        return bool(d and d.get("frames"))

    newLayerNext = Property(bool, lambda self: self._new_layer, notify=targetChanged)

    @Slot()
    def newPaintLayer(self):
        """The next stroke starts a new paint layer on top (paint.stroke layer "new"); pressed again: not."""
        self._new_layer = not self._new_layer
        self._refresh()

    # ---- the pen: one stroke = one gesture = one change -----------------------------------------------------
    @Slot(float, float, float, result=bool)
    def beginStroke(self, x, y, pressure):
        """x, y in composition px (like Bridge2D.pickAt); pressure 0..1 (1 for a mouse)."""
        d = self._aim()
        if d is None and self.b.tool != "draw" or self._erasing() and not self.canErase:
            return False                    # the eraser never makes a layer: with nothing to erase it does nothing
        self.endStroke()
        c = self.b.comp()
        make = None
        if d is None:                       # Draw tool, no drawing selected: the first stroke makes the drawing layer too
            make, lid = adding.new_drawing_at(self.b.doc, c, x, y, frame_number(self.b.time, c["fps"]) if self.b._paint_layers.fresh_each else None)
            d = {"id": lid}
        layer = "new" if self._new_layer else self.b._paint_layers.current()     # the highlighted paint layer

        fill, through = (d, self.through()) if self.through() is not None else (None, None)
        if through is not None:             # painting in place: the stroke goes through the element into its painting
            d = through

        def go():
            if not make:
                check_showing(self.b.doc.item(d["id"]), self.b.own_t(d["id"]), self.b.time)
            args = self.brush.stroke_args()
            with self.b.frames.asking():    # the made layer's place is asked before its first picture is drawn
                self._stroke = s = StrokeDrag(self.b.doc, self.b.who, d["id"], self.b.time if make else self.b.own_t(d["id"]),
                                              c["fps"], args, x, y, self.b.place_of, pressure, make, layer, self.tilt.lean(),
                                              True, fill)
            settled = self.b.opened.shows_now if self.b.opened.on else None     # opened: its own picture lands
            smear = (args.get("smudge") and args.get("mode") != "erase"
                     and (smear_ink(self._wet, args, s, self.b.selBox, self._n()) if fill is None
                          else wet_through.smear(self._wet, args, s, fill, self._n())))
            if smear:                       # a smudge smears the paint it is on (its own, or its painting's: wet.py)
                self._wet.start(smear, settled=settled)
                self._wet.add(*s.points[-1][:3])
            elif fill is not None and args.get("mode") != "erase" and (uses := wet_uses.uses(
                    self.b, fill, [through["id"], *fill_aim.others_in(self.b.comp(), fill["id"], through["id"])])):
                ink = self._wet.ink(args, s.sid, 1.0)              # in the painting's px, on every layer using it
                if s._map.tiled:
                    kx, ky = wet_uses.start_tile(s)
                    ink.shift = (-kx * s._map.pw, -ky * s._map.ph)
                self._wet.start(ink, None, settled, [{**u, "pad": math.ceil(ink.reach) + 2} for u in uses])
                self._wet.add(*s.points[-1][:3])
            else:
                ink = self._wet.ink(args, s.sid, s.scale(x, y))         # world px: anywhere on the canvas
                wraps = fill is not None and paintings.seamless(fill)
                self._wet.start(ink, (lambda: wet_wrap.copies(s, fill, args.get("size", 10))) if wraps else None, settled)
                self._wet.add(x, y, pressure)
                if ink.erasing:
                    self._ask_reveal(ink, d["id"], x, y, fill is not None)
            self._wet.show()
            if make:
                self._fresh = None
                self.b._paint_layers.fresh_each = False       # its Draw each frame is on the layer now
                self._select_made.ask(d["id"])  # the ink first; the layer picked (panels, rows) the frame after
        return self.b.guard(go)

    @Slot(float, float, float)
    def strokeTo(self, x, y, pressure):
        s = self._stroke
        if s is None:
            return
        n = len(s.points)
        if not self.b.guard(lambda: s.move(x, y, pressure, self.tilt.lean())):
            return
        if s.wet:
            self._wet_add(s, n, x, y, pressure)
        if not self._showing:
            self._showing = True                    # after the moves already queued: one picture for all of them
            QTimer.singleShot(0, self._show_stroke)

    def _show_stroke(self):
        self._showing = False
        s = self._stroke
        if s is not None:
            self.b.guard(self._wet.show if s.wet else s.show)

    wet = Property(QObject, lambda self: self._wet, constant=True)

    def _ask_reveal(self, ink, layer_id, x, y, fill=False):
        """The eraser's ink shows the world the canvas shows without the layer it erases: the one drawn ahead when it
        is still right, else asked of the canvas's engine now, off this thread; its ink shows once it comes (wet.py)."""
        if self.b.opened.on:                # opened on its own: under the painting is the empty canvas
            return self._wet.reveal(ink, *wet_through.bare(self.b.world.visible(), x, y))
        kept = self.ahead and self.ahead.ready(layer_id, fill, x, y)   # drawn before the press (reveal_ahead.py)
        if kept is not None:
            return self._wet.reveal(ink, *kept)
        scene = without_paint(self.b._scene, layer_id, fill) if self.b._scene else None
        if scene is None:
            raise RuntimeError("the canvas can't be drawn right now, so there is nothing to erase (see the status line)")
        rect = reveal_rect(self.b.world.visible(), x, y)
        self.b.frames.still(scene, self.b.time, self.b.play.samples(),
                            lambda px, e: self._revealed.emit(ink, (px, (rect["x"], rect["y"])), e), rect)

    def _reveal(self, ink, got, error):
        if error is not None:
            self.b._fail(f"Error: the eraser can't show what is under the layer: {error}")
        else:
            self._wet.reveal(ink, *got)

    def _wet_add(self, s, n, x, y, pressure):
        """The move's point to the wet ink: a smudge's in canvas px, as the stroke took it (if it did)."""
        if not self._wet.in_canvas:
            self._wet.add(x, y, pressure)
        elif len(s.points) > n:
            self._wet.add(*s.points[-1][:3])

    @Slot()
    def endStroke(self):
        self._select_made.flush()                   # a release before the press's frame came: the made layer picked first
        s, self._stroke = self._stroke, None
        if s is not None:
            saved = self.b.guard(lambda: self._saved(s.end()))
            if s.wet:
                self._wet.lift(saved)
            if saved:
                self._new_layer = False             # the new paint layer is made: later strokes go on it
            self._refresh()

    def _saved(self, change):
        """The stroke's change done; a stroke the drawing couldn't hold started a new one: the status line says so."""
        self.b.done(change, "")
        said = paint_overflow.note(change, self.b.doc) if change is not None else None
        if said:
            self.b._set_status(said)

    # ---- frame by frame (screen shortcuts and buttons; each is one change) -----------------------------------
    def _frame_edit(self, make):
        d = self.drawing()
        if d is not None:
            calls, label = make(d)
            return self.b.guard(lambda: self.b.done(self.b.doc.apply(calls, self.b.who, label=label), ""))
        return False

    @Slot(bool)
    def newFrame(self, copy):
        """New (Alt+N) or Copy (Alt+Shift+N): the playhead goes to the new drawing, so the next stroke lands in it."""
        d = self.drawing()
        if d is None:
            return
        calls, label, at = framing.new_frame(d, self._n(), copy)
        if self._frame_edit(lambda _d: (calls, label)) is not False:
            self._go(at, d["id"])

    @Slot(str, int)
    def holdFrame(self, frame_id, frames):
        """A cell's right edge dragged: that drawing held this many frames (later ones move with it)."""
        self._frame_edit(lambda d: ([{"op": "frame.hold", "target": [frame_id], "args": {"frames": max(1, frames)}}],
                                    "Hold drawing"))

    @Slot(str, int)
    def moveFrame(self, frame_id, to):
        """A cell dragged to another frame (frame.move): the others stay."""
        self._frame_edit(lambda d: ([{"op": "frame.move", "target": [frame_id], "args": {"to": max(0, to)}}],
                                    "Move drawing"))

    @Slot(str, int)
    def copyFrameTo(self, frame_id, at):
        """Alt+drag a cell: a copy of that drawing at another frame (a reused drawing, for cycles)."""
        self._frame_edit(lambda d: ([{"op": "frame.add", "target": [d["id"]], "args": {"at": max(0, at), "copy": frame_id}}],
                                    "Copy drawing"))

    @Slot(str)
    def removeFrame(self, frame_id):
        """Delete a cell: the drawing before is held over the gap."""
        self._frame_edit(lambda d: ([{"op": "frame.remove", "target": [frame_id]}], "Delete drawing"))

    @Slot(int)
    def setNewHold(self, frames):
        """New ones hold 1 · 2 · 3 · 4: a setting of the layer (newHold), so agents' frame.add lands the same way."""
        self._frame_edit(lambda d: ([{"op": f'{d["type"]}.set', "target": [d["id"]], "args": {"newHold": frames}}],
                                    "New ones hold"))

    @Slot(int)
    def goToFrame(self, at):
        """A cell clicked: the playhead to where that drawing starts (it is the one painted into)."""
        d = self.drawing()
        if d is not None:
            self._go(at, d["id"])

    def _go(self, at, layer):
        """The playhead to where drawing frame `at` shows: on the layer (its own frames), or, painting a painted fill
        in place, where that layer next shows the painting's drawing at `at`."""
        through, fps = self.through(), self.b.comp()["fps"]
        if through is not None:
            own = frame_number(self.b.own_t(through["id"]), fps)
            at, layer = painted_fill.when_shown(through, self._aim(), at, own, fps), through["id"]
        self.b.setTime(at / fps + self.b.offset(layer))

    @Slot()
    def clearDrawing(self):
        """Wipe the drawing at the playhead (every paint layer's strokes) to redraw it: one change."""
        def calls(d):
            here = frame_at(d, self._n())
            return [{"op": "paint.clear", "target": [p["id"] for p in here["paints"]]}] if here else [], "Clear drawing"
        self._frame_edit(calls)

    @Slot(int)
    def holdBy(self, delta):
        self._frame_edit(lambda d: framing.hold(d, self._n(), delta))

    @Slot(int)
    def goFrame(self, direction):
        """-1 previous drawing, +1 next: the playhead jumps to where it starts."""
        d = self.drawing()
        at = framing.state(d, self._n())["prev" if direction < 0 else "next"] if d else None
        if at is not None:
            self._go(at, d["id"])

    @Slot(int, result=int)
    def flipFrame(self, direction):
        """Hold , or . (FlipThrough.qml): the next / previous drawing, round at the ends; the frames until the next flip."""
        d = self.drawing()
        got = framing.flip(d, self._n(), direction) if d else None
        if got is None:
            return 0
        self._go(got[0], d["id"])
        return got[1]

    @Slot(bool)
    def setOnion(self, on):
        self._onion, self._built = on, None
        self._refresh()

    @Slot(str, int)
    def setOnionReach(self, side, count):
        """Onion skin › Before / After: 0 – 5 drawings that way."""
        self._reach[side], self._built = max(0, min(5, count)), None
        self._refresh()

    # ---- inside -----------------------------------------------------------------------------------------------
    def _tilt_pen(self):
        """A tilting pen showed up: the brush panel gains Tilt → angle / size."""
        self.brush.tilt_pen = self.tilt.has_tilt
        self._rows_changed()

    def _doc_changed(self):
        self._rev += 1

    _seen = None                                    # (document, target, the rest): what _refresh last worked from

    def _paint_state(self):
        """Everything the painter's properties are worked out from. A pick that leaves it as it was (from one text to
        another: nothing to paint on either way) changes nothing the painter shows."""
        t, op = self.target(), self.b.opened
        rest = (op.on, op.frame() if op.on else None, self._fresh is not None and self._fresh == self.b.selectedLayer,
                self.b._t if t is not None else None, self._onion, tuple(self._reach.items()),
                tuple(sorted(self._on_fill.items())), self._new_layer, self._serial, self._built, self._stroke is None,
                self.b.comp_id, id(self.b.marks.times) if self.b.marks else None)
        return self.b.doc.data, t, rest

    def _refresh(self):
        """The outline or the playhead moved: announced only when what QML reads of the painter changed (sent on every
        edit and every frame of a scrub, it re-ran the paint panel, the brush header and the frame marks: ~5 ms), and
        then only that group (_GROUPS). Worked out only when what it is worked out from moved (_paint_state)."""
        self._soon.cancel()
        state, seen = self._paint_state(), self._seen
        if seen is not None and seen[0] is state[0] and seen[1] is state[1] and seen[2] == state[2]:
            return
        self._seen = state
        if self._stroke is None:                    # not while a stroke is being drawn: the neighbours don't change
            self._rebuild_onion()
        for i, (signal, names) in enumerate(self._GROUPS):
            told = tuple(getattr(self, n) for n in names)
            if told != self._told[i]:
                self._told[i] = told
                getattr(self, signal).emit()

    def _rebuild_onion(self):
        d = self._cells()
        if not (self._onion and d):
            return
        here = frame_at(d, self._n())
        key = (d["id"], here and here["id"], self._rev)
        if key == self._built:
            return
        image = onion.build(d, self._n(), self._reach["before"], self._reach["after"])
        self._built = key
        self.provider.put(image if image is not None else onion.QImage())
        self._serial += 1
