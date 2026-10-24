"""Wet ink: the stroke being drawn, shown at once over the canvas while the pen is down (image://wet/<n>).

The pen's stroke goes into the document once, when it lifts (strokes.StrokeDrag, `wet=True`). Until then this draws
it with the painting kit's own brush (`canvas.stamp`, the same stamp a saved stroke gets), in composition px, a few
points at a time (WetInk), so no move waits for the scene to be described and drawn again. The saved
stroke is then drawn by the one render path (preview ≡ export); the wet picture goes when that frame lands.
A smudging brush smears the layer's own paint: its wet ink works on that paint (`under`, in the paint canvas's px,
laid over the layer's box like the onion skin) and shows the region smeared. Erasing can't be shown over the picture (what lies under the erased paint isn't in it): it keeps
drawing through the document (`shows`).
"""
from __future__ import annotations

import math
import threading

import numpy as np
from PySide6.QtCore import Property, QObject, Signal
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider
from rostrum_paint import canvas, compose
from rostrum_paint.ops import build, seed_of

PAD = 4                     # px round the stroke's box, for the brush's soft edge and jitter
CHUNK = 12                  # the fewest points in the tip before the dry part is stamped again


def shows(brush: dict) -> bool:
    """Whether wet ink can show a stroke made with these settings (not erasing)."""
    return brush.get("mode", "normal") != "erase"


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


class WetInk:
    """One stroke's wet pictures. `scale`: canvas px per composition px (the brush size is in canvas px). Each look
    stamps only the newest points (the tip) over the dry part; once the tip is a quarter of the stroke (CHUNK points
    at least) the dry part is stamped again from the whole stroke so far, as the saved stroke will be: no seams, and
    the cost per point stays flat (the dry part is redone each time the stroke grows by a quarter). `under`: for a smudging brush, the layer's paint (premultiplied, its canvas px: then
`bounds` is the canvas size, points come in canvas px and `place` = (x, y, x scale, y scale) puts canvas px on the
composition)."""

    def __init__(self, brush: dict, sid: str, scale: float, bounds: tuple[int, int], under: np.ndarray | None = None,
                 place=(0.0, 0.0, 1.0, 1.0)):
        self.brush, self.sid, self.scale, self.bounds = brush, sid, scale or 1.0, bounds
        self.size = brush.get("size", 10) / self.scale
        self.reach = self.size / 2 + PAD + 3 * brush.get("jitter", 0) * self.size
        self.points: list[list[float]] = []
        self.smears, self.place = under is not None, place
        self._base = under                                              # what the stroke starts on (None: nothing)
        self._dry = under.copy() if under is not None else np.zeros((bounds[1], bounds[0], 4), np.float32)
        self._settled, self._dry_box = 0, None                          # points in the dry part; its box (x0, y0, x1, y1)

    def add(self, x: float, y: float, pressure: float):
        self.points.append([x, y, round(min(max(pressure, 0.0), 1.0), 3)])

    def _box(self, pts) -> tuple[int, int, int, int] | None:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        x0, y0 = max(0, math.floor(min(xs) - self.reach)), max(0, math.floor(min(ys) - self.reach))
        x1 = min(self.bounds[0], math.ceil(max(xs) + self.reach))
        y1 = min(self.bounds[1], math.ceil(max(ys) + self.reach))
        return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None

    def _tip(self) -> list:
        return self.points[max(0, self._settled - 1):]

    def _stamp(self, into, origin, pts):
        item = build("stroke", self.sid, {**self.brush, "size": self.size, "seed": seed_of(self.sid),
                                          "points": [[x - origin[0], y - origin[1], p] for x, y, p in pts]})
        canvas.stamp(into, item, into.shape[1], into.shape[0], {}, into[..., :3].copy() if item["smudge"] else None)

    def settle(self) -> bool:
        """The dry part stamped again from the whole stroke so far, once the tip is long enough; True if it changed."""
        if len(self._tip()) < max(CHUNK, len(self.points) // 4):
            return False
        box = self._box(self.points)
        if box:
            x0, y0, x1, y1 = box
            base = self._base[y0:y1, x0:x1] if self._base is not None else None
            part = base.copy() if base is not None else np.zeros((y1 - y0, x1 - x0, 4), np.float32)
            self._stamp(part, (x0, y0), self.points)
            self._dry[y0:y1, x0:x1] = part
            self._dry_box = box
        self._settled = len(self.points)
        return True

    def dry(self) -> tuple[QImage, dict] | None:
        return None if self._dry_box is None else self._placed(*_picture(self._dry, self._dry_box))

    def tip(self) -> tuple[QImage, dict] | None:
        tip = self._tip()
        box = self._box(tip) if tip else None
        if box is None:
            return None
        x0, y0, x1, y1 = box
        px = (self._dry[y0:y1, x0:x1].copy() if self.smears        # a smudge's tip: the picture there, smeared
              else np.zeros((y1 - y0, x1 - x0, 4), np.float32))
        self._stamp(px, (x0, y0), tip)
        return self._placed(*_picture(px, (0, 0, x1 - x0, y1 - y0), (x0, y0)))

    def _placed(self, image, box):
        ox, oy, kx, ky = self.place
        return image, {"x": ox + box["x"] * kx, "y": oy + box["y"] * ky, "w": box["w"] * kx, "h": box["h"] * ky}


def _picture(px, box, at=None) -> tuple[QImage, dict]:
    """The part `box` (x0, y0, x1, y1) of premultiplied pixels as a straight-alpha picture, and where it goes."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    u8 = np.ascontiguousarray(compose.straight8(px[y0:y1, x0:x1]))
    ax, ay = at or (x0, y0)
    return QImage(u8.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy(), {"x": ax, "y": ay, "w": w, "h": h}


class WetView(QObject):
    """The screen's wet ink, read in QML as `painter.wet`: the tip's `serial` (0: none showing) and `box`, the dry
    part's `drySerial` and `dryBox` (composition px)."""
    changed = Signal()

    def __init__(self, frame_changed, parent=None):
        super().__init__(parent)
        self.provider, self._ink, self._serial, self._box, self._lifted = WetProvider(), None, 0, {}, False
        self._dry_serial, self._dry_box = 0, {}
        frame_changed.connect(self._frame)

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

    def show(self):
        if self._ink is None:
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

    def _frame(self):
        if self._lifted:
            self._clear()

    def _clear(self):
        self._lifted = False
        if self._serial or self._dry_serial:
            self._serial, self._box, self._dry_serial, self._dry_box = 0, {}, 0, {}
            self.changed.emit()


def smear_ink(brush: dict, stroke, box: dict, n: int) -> WetInk:
    """A smudging stroke's wet ink: on the layer's own paint at the playhead (its drawing there, in canvas px), laid
    over the layer's box on the composition (`box`: the bridge's selBox), as the onion skin is."""
    from rostrum2d.drawing import frame_at, paint_size
    item = stroke.item
    w, h = paint_size(item, stroke.props)
    here = frame_at(item, n) if item.get("frames") else None
    paint = canvas.render(here, w, h).rgba.copy() if here else np.zeros((h, w, 4), np.float32)
    place = (box.get("x", 0), box.get("y", 0), box.get("w", w) / w, box.get("h", h) / h)
    return WetInk(brush, stroke.sid, 1.0, (w, h), np.ascontiguousarray(paint, np.float32), place)
