"""Wet ink: the stroke being drawn, shown at once over the canvas while the pen is down (image://wet/<n>).

The pen's stroke goes into the document once, when it lifts (strokes.StrokeDrag, `wet=True`). Until then this draws
it with the painting kit's own brush (wet_ink.py), so no move waits for the scene to be described and drawn again. The
saved stroke is then drawn by the one render path (preview ≡ export); the wet picture goes when that frame lands.
A smudging brush smears the layer's own paint: its wet ink works on that paint (`under`, in the paint canvas's px,
laid on the world by the stroke's own place) and shows the region smeared, over the world under the layer (the smear
holds the layer's paint, so it replaces it rather than lying on it again). Ink on a layer shows in the layer's place:
each wet box over the world under the stroke and under the layers above (`layer`, wet_layers.py, WetInk.qml). The
eraser's wet ink shows, where it lies, the world drawn without the layer it erases. Those pictures are asked of the
canvas's engine at the press (or drawn ahead: reveal_ahead.py): the part of the world the canvas shows, at 1 px per
world px, at most MOST_REVEAL px a side round the press (`reveal_rect`). Wet ink lies in world px, anywhere on the
endless canvas, the frame at home or not.
"""
from __future__ import annotations

import math
import threading
from concurrent.futures import Future, ThreadPoolExecutor

import numpy as np
from PySide6.QtCore import Property, QObject, Signal
from PySide6.QtGui import QImage
from rostrum_gui.screen_images import ScreenImages
from rostrum_paint import canvas

from .wet_ink import WetInk
from .wet_tip import picture_of

MOST_REVEAL = 8192           # the engine's largest picture side


class WetProvider(ScreenImages):
    """image://wet/tip-<n> (the stroke drawn so far) and image://wet/dry-<n> (a Fill's or a paste's flat colour)."""

    def __init__(self):
        super().__init__()
        self._lock, self._images = threading.Lock(), {"dry": QImage(), "tip": QImage()}

    def put(self, part: str, image: QImage):
        with self._lock:
            self._images[part] = image

    def picture(self, id_):
        with self._lock:
            return self._images.get(id_.split("-")[0], QImage())


class WetView(QObject):
    """The screen's wet ink, read in QML as `painter.wet`: the stroke's `serial` (0: none showing) and `box`, a flat
    colour's `drySerial` and `dryBox` (world px)."""
    changed = Signal()
    _dried = Signal()            # a piece was stamped on the ink's thread: take it in (on the screen's thread)

    def __init__(self, frame_changed, parent=None):
        super().__init__(parent)
        self.provider, self._ink, self._serial, self._box, self._lifted = WetProvider(), None, 0, {}, False
        self._ending = None                             # a lifted stroke's ink, drawing the points it hadn't yet
        self._dry_serial, self._dry_box, self._settled = 0, {}, lambda: True
        self._copies, self._copies_of = [], None        # a seamless painting's wrapped copies (wet_wrap.py)
        self._uses = []                                 # ink in a painting's px, on every layer using it (wet_uses.py)
        self._layered, self._layer_n = {}, 0            # the world under the stroke and the layers above (wet_layers.py)
        frame_changed.connect(self._frame)
        self._dried.connect(self.show)

    def ink(self, brush: dict, sid: str, scale: float, bounds=None, under=None, place=(0.0, 0.0, 1.0, 1.0)) -> WetInk:
        """A stroke's ink, telling this view when a piece is ready (from the ink's thread). `bounds`: a smear's
        canvas size (normal ink has none: it goes anywhere in the world)."""
        return WetInk(brush, sid, scale, bounds, under, place, brush.get("mode") == "erase", self._dried.emit)

    serial = Property(int, lambda self: self._serial, notify=changed)
    box = Property("QVariantMap", lambda self: self._box, notify=changed)            # the tip's
    drySerial = Property(int, lambda self: self._dry_serial, notify=changed)
    dryBox = Property("QVariantMap", lambda self: self._dry_box, notify=changed)
    copies = Property("QVariantList", lambda self: self._copies, notify=changed)    # [{x, y}] moves of both pictures
    layeredChanged = Signal()       # its own: asked once a stroke
    layered = Property("QVariantMap", lambda self: self._layered, notify=layeredChanged)   # {under, above: {serial, x, y, w, h}}
    usesChanged = Signal()          # its own: the uses are laid out once a stroke, not at each move
    uses = Property("QVariantList", lambda self: self._uses, notify=usesChanged)    # [{own, w, h, pw, ph, inner, offsets, clip}]

    def start(self, ink: WetInk, copies_of=None, settled=None, uses=None):
        """`copies_of()`: where else the ink shows (wet_wrap.copies), asked at each look; None: nowhere else.
        `settled()`: whether the picture with the saved stroke is shown (default: the frame that lands has it).
        `uses`: the ink is in a painting's px and shows on these layers (wet_uses.uses), not where it lies."""
        self._ink, self._ending, self._lifted, self._copies_of = ink, None, False, copies_of
        if self._layered:
            self._layered = {}
            self.layeredChanged.emit()
        if self._uses or uses:
            self._uses = list(uses or [])
            self.usesChanged.emit()
        self._settled = settled or (lambda: True)

    @property
    def smearing(self) -> bool:
        return self._ink is not None and self._ink.smears

    @property
    def in_canvas(self) -> bool:
        """The ink's points are the stroke's own (canvas px: a smear, or a painting's ink shown on its uses)."""
        return self._ink is not None and (self._ink.smears or bool(self._uses))

    def add(self, x, y, pressure):
        if self._ink is not None:
            self._ink.add(x, y, pressure)

    def reveal(self, ink: WetInk, frame: np.ndarray, origin: tuple[int, int]):
        """The world without the erased layer came (its top-left at world px `origin`): the eraser's ink shows from
        now on."""
        if ink is self._ink:
            ink.reveal_with(frame, origin)
            self.show()

    def layer(self, ink: WetInk, got: dict):
        """The pictures that put the ink in its layer's place came ({"under" | "above": (straight RGBA8, world top-left)},
        wet_layers.py): from now on each wet box shows the world under the stroke, the ink, then the layers above it.
        A smear waits for `under` (its pictures hold the layer's paint: on the world as shown it would count twice)."""
        if ink is not self._ink or not got:
            return
        out, self._layer_n = {}, self._layer_n + 1
        for part, (px, (x, y)) in got.items():
            if part == "under":                         # opaque: it replaces the world in the box
                rgba = np.empty(px.shape[:2] + (4,), np.uint8)
                rgba[..., :3], rgba[..., 3] = px[..., :3], 255
                px = rgba
                ink.reveal_with(px, (x, y))
            self.provider.put(part, picture_of(px))
            out[part] = {"serial": self._layer_n, "x": x, "y": y, "w": px.shape[1], "h": px.shape[0]}
        self._layered = out
        self.layeredChanged.emit()
        self.show()

    def show(self):
        ink = self._ink or self._ending
        if ink is None or not ink.ready:
            return
        got = ink.tip()
        if got is not None and got[0] is not self.provider.picture("tip"):     # (unchanged: the same picture)
            self.provider.put("tip", got[0])
            self._serial, self._box = self._serial + 1, got[1]
        if ink is self._ending and ink.whole:
            self._ending = None
        if self._copies_of is not None:
            self._copies = self._copies_of()
            if ink.erasing:           # each copy shows what is under it there, not what is under the pen
                self._copies = [{**c, "own": i} for i, c in enumerate(self._copies)]
                for i, c in enumerate(self._copies):
                    for part, box in (("dry", self._dry_box), ("tip", self._box)):
                        image = self.provider._images.get(part)
                        if box and image is not None and not image.isNull():
                            self.provider.put(f"{part}c{i}", ink.moved(image, box, c["x"], c["y"]))
        self.changed.emit()

    def lift(self, saved: bool):
        """The pen is up: the wet picture stays until the frame with the saved stroke lands (or goes now, if the
        stroke wasn't saved). Meanwhile the ink draws the points it hadn't yet and the stroke's end (`_ending`), so the
        whole stroke shows within a piece of the release, not when the saved stroke's frame lands."""
        ink, self._ink, self._lifted = self._ink, None, True
        if not saved:
            self._clear()
        elif ink is not None:
            self._ending = ink
            ink.lift()
            self.show()

    def flat(self, got, settled=lambda: True):
        """A Fill's or a paste's flat colour (flat_cue.draw's (image, box)) shows at once; the frame with the real paint
        takes it away when it lands, like a lifted stroke's wet ink. Nothing to show (None): nothing changes."""
        if got is None or self._ink is not None:
            return
        self.provider.put("dry", got[0])
        self._dry_serial, self._dry_box, self._lifted, self._settled = self._dry_serial + 1, got[1], True, settled
        self.changed.emit()

    def _frame(self):
        if self._lifted and self._settled():
            self._clear()

    def landed(self):
        """A picture outside the frame landed (an opened painting's): the lifted ink goes if it shows the stroke."""
        self._frame()

    def _clear(self):
        self._lifted, self._ending = False, None
        self._copies_of = None
        if self._layered:
            self._layered = {}
            self.layeredChanged.emit()
        if self._serial or self._dry_serial or self._copies or self._uses:
            self._serial, self._box, self._dry_serial, self._dry_box, self._copies = 0, {}, 0, {}, []
            if self._uses:
                self._uses = []
                self.usesChanged.emit()
            self.changed.emit()


def reveal_rect(visible: dict | None, x: float, y: float) -> dict:
    """The world rectangle the eraser's reveal is drawn for (scale 1, whole px): what the canvas shows (`visible`,
    world_view.visible()), at most MOST_REVEAL px a side round the press at x, y; the press's own square without a view."""
    half = MOST_REVEAL // 2 - 1
    x0, y0, x1, y1 = x - half, y - half, x + half, y + half
    if visible:
        x0, y0 = max(x0, visible["x"]), max(y0, visible["y"])
        x1, y1 = min(x1, visible["x"] + visible["w"]), min(y1, visible["y"] + visible["h"])
    x0, y0 = math.floor(x0), math.floor(y0)
    return {"x": x0, "y": y0, "w": max(1, math.ceil(x1) - x0), "h": max(1, math.ceil(y1) - y0), "scale": 1.0}


def smear_ink(view: WetView, brush: dict, stroke, n: int) -> WetInk:
    """A smudging stroke's wet ink: on the layer's own paint at the playhead (its drawing there, in canvas px), laid
    on the world where the stroke's own place (strokes.StrokeDrag.place, the one mapping its points went through) puts
    the canvas: a drawing the stroke just made has no box on screen yet. A drawing's smear goes past its canvas (the
    drawing grows with the stroke: rostrum2d/paint_grow.py); an element's paint stays in its box."""
    from rostrum2d.drawing import frame_at, paint_size
    from rostrum2d.placement import comp_point
    item, place = stroke.item, stroke.place
    w, h = paint_size(item, stroke.props)
    here = frame_at(item, n) if item.get("frames") else None
    (ox, oy), (ax, _), (_, ay) = (comp_point(place, 0, 0), comp_point(place, place["w"] / w, 0),
                                  comp_point(place, 0, place["h"] / h))
    bounds = None if item["type"] == "drawing" else (w, h)
    return view.ink(brush, stroke.sid, 1.0, bounds, paint_under(here, w, h), (ox, oy, ax - ox, ay - oy))


_UNDER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="wet-under")


def paint_under(frame: dict | None, w: int, h: int) -> Future:
    """A smear's paint (a drawing's frame, premultiplied, only read) made off the screen's thread: a press never waits
    for a drawing's pixels (they are usually kept already; just after a stroke they may still be being made)."""
    if frame is None:
        done = Future()
        done.set_result(np.zeros((h, w, 4), np.float32))
        return done
    return _UNDER.submit(lambda: np.ascontiguousarray(canvas.render(frame, w, h).rgba, np.float32))
