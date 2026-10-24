"""Wet ink: the stroke being drawn, shown at once over the canvas while the pen is down (image://wet/<n>).

The pen's stroke goes into the document once, when it lifts (strokes.StrokeDrag, `wet=True`). Until then this draws
it with the painting kit's own brush (wet_ink.py), so no move waits for the scene to be described and drawn again. The
saved stroke is then drawn by the one render path (preview ≡ export); the wet picture goes when that frame lands.
A smudging brush smears the layer's own paint: its wet ink works on that paint (`under`, in the paint canvas's px,
laid over the layer's box like the onion skin) and shows the region smeared. The eraser's wet ink shows, where it
lies, the world drawn without the layer it erases (asked of the canvas's engine at the press: the part of the world
the canvas shows, at 1 px per world px, at most MOST_REVEAL px a side round the press: `reveal_rect`). Wet ink lies
in world px, anywhere on the endless canvas, the frame at home or not.
"""
from __future__ import annotations

import math
import threading

import numpy as np
from PySide6.QtCore import Property, QObject, Signal
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider
from rostrum_paint import canvas

from .wet_ink import WetInk

MOST_REVEAL = 8192           # the engine's largest picture side


class WetProvider(QQuickImageProvider):
    """image://wet/dry-<n> (the stroke's settled part) and image://wet/tip-<n> (its newest points)."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._lock, self._images = threading.Lock(), {"dry": QImage(), "tip": QImage()}

    def put(self, part: str, image: QImage):
        with self._lock:
            self._images[part] = image

    def requestImage(self, id_, size, requested):  # noqa: N802 (Qt's name)
        with self._lock:
            return self._images[id_.split("-")[0]]


class WetView(QObject):
    """The screen's wet ink, read in QML as `painter.wet`: the tip's `serial` (0: none showing) and `box`, the dry
    part's `drySerial` and `dryBox` (world px)."""
    changed = Signal()
    _dried = Signal()            # a dry part was stamped on the worker thread: take it in (on the screen's thread)

    def __init__(self, frame_changed, parent=None):
        super().__init__(parent)
        self.provider, self._ink, self._serial, self._box, self._lifted = WetProvider(), None, 0, {}, False
        self._dry_serial, self._dry_box, self._settled = 0, {}, lambda: True
        frame_changed.connect(self._frame)
        self._dried.connect(self.show)

    def ink(self, brush: dict, sid: str, scale: float, bounds=None, under=None, place=(0.0, 0.0, 1.0, 1.0)) -> WetInk:
        """A stroke's ink, telling this view when a dry part is ready (from the worker thread). `bounds`: a smear's
        canvas size (normal ink has none: it goes anywhere in the world)."""
        return WetInk(brush, sid, scale, bounds, under, place, brush.get("mode") == "erase", self._dried.emit)

    serial = Property(int, lambda self: self._serial, notify=changed)
    box = Property("QVariantMap", lambda self: self._box, notify=changed)            # the tip's
    drySerial = Property(int, lambda self: self._dry_serial, notify=changed)
    dryBox = Property("QVariantMap", lambda self: self._dry_box, notify=changed)

    def start(self, ink: WetInk):
        self._ink, self._lifted = ink, False

    @property
    def smearing(self) -> bool:
        return self._ink is not None and self._ink.smears

    def add(self, x, y, pressure):
        if self._ink is not None:
            self._ink.add(x, y, pressure)

    def reveal(self, ink: WetInk, frame: np.ndarray, origin: tuple[int, int]):
        """The world without the erased layer came (its top-left at world px `origin`): the eraser's ink shows from
        now on."""
        if ink is self._ink:
            ink.reveal_with(frame, origin)
            self.show()

    def show(self):
        if self._ink is None or not self._ink.ready:
            return
        if self._ink.settle():
            got = self._ink.dry()
            if got is not None:
                self.provider.put("dry", got[0])
                self._dry_serial, self._dry_box = self._dry_serial + 1, got[1]
        got = self._ink.tip()
        if got is not None:
            self.provider.put("tip", got[0])
            self._serial, self._box = self._serial + 1, got[1]
        self.changed.emit()

    def lift(self, saved: bool):
        """The pen is up: the wet picture stays until the frame with the saved stroke lands (or goes now, if the
        stroke wasn't saved)."""
        self._ink, self._lifted = None, True
        if not saved:
            self._clear()

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

    def _clear(self):
        self._lifted = False
        if self._serial or self._dry_serial:
            self._serial, self._box, self._dry_serial, self._dry_box = 0, {}, 0, {}
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


def without_paint(scene: dict, layer_id: str) -> dict | None:
    """The scene with that layer's paint left out (a drawing draws nothing; an element still draws its own look);
    None if the layer isn't in it. Only the nodes on the way are copied (the scene is shared)."""
    def walk(node):
        if node.get("id") == layer_id:
            out = {k: v for k, v in node.items() if k != "paint"}
            if node["type"] == "drawing":
                out["frames"] = []
            return out
        for key, kids in node.items():
            if isinstance(kids, list):
                for i, kid in enumerate(kids):
                    got = walk(kid) if isinstance(kid, dict) and "type" in kid else None
                    if got is not None:
                        return {**node, key: kids[:i] + [got] + kids[i + 1:]}
        return None
    comp = walk(scene["comp"])
    return None if comp is None else {**scene, "comp": comp}


def smear_ink(view: WetView, brush: dict, stroke, box: dict, n: int) -> WetInk:
    """A smudging stroke's wet ink: on the layer's own paint at the playhead (its drawing there, in canvas px), laid
    over the layer's box on the composition (`box`: the bridge's selBox), as the onion skin is."""
    from rostrum2d.drawing import frame_at, paint_size
    item = stroke.item
    w, h = paint_size(item, stroke.props)
    here = frame_at(item, n) if item.get("frames") else None
    paint = canvas.render(here, w, h).rgba.copy() if here else np.zeros((h, w, 4), np.float32)
    place = (box.get("x", 0), box.get("y", 0), box.get("w", w) / w, box.get("h", h) / h)
    return view.ink(brush, stroke.sid, 1.0, (w, h), np.ascontiguousarray(paint, np.float32), place)
