"""The paint layer list's thumbnails (painting design §2.3, mockup paint-02): each paint layer's own pixels, small, see-through
(image://paintthumbs/<key>; PaintOn.qml lays them on mid-grey squares, so ink of any colour reads). Drawn by the painting kit
(`canvas.layer_rgba`, the same pixels a render uses), kept per layer content (`canvas.layer_key`, cheap), so a layer is
drawn again only after it changed. Drawing one costs a whole canvas, so it is done off the GUI thread: meanwhile the
layer's last thumbnail stands in under the new name, and `ready` says when the new one is there (the list asks again).
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QImage
from rostrum_gui.screen_images import ScreenImages
from rostrum_paint import canvas

SIDE = 48          # px: twice the row's thumbnail box, so it stays sharp on a high-density screen
KEEP = 64
_DRAW = ThreadPoolExecutor(max_workers=1, thread_name_prefix="paint-thumbs")


class ThumbsReady(QObject):
    ready = Signal()     # a thumbnail was drawn (emitted on the worker thread, heard on the GUI's)


class ThumbProvider(ScreenImages):
    def __init__(self):
        super().__init__()
        self._lock, self._images, self._last, self._asked = threading.Lock(), {}, {}, set()
        self._want: dict[str, str] = {}                 # paint id -> the thumbnail name its list row asked for last
        self.notes, self.drawn = ThumbsReady(), 0       # drawn: how many so far (a new one: the list's sources change)

    def source(self, frame: dict, paint: dict, w: int, h: int) -> str:
        """The thumbnail's image:// address for this layer's content (its last one stands in until it is drawn)."""
        return f"image://paintthumbs/{self.key(frame, paint, w, h)}/{paint['id']}?{self.drawn}"

    def key(self, frame: dict, paint: dict, w: int, h: int) -> str:
        """The thumbnail's name for this layer's content; drawn off the GUI thread when it isn't kept yet."""
        k = canvas.layer_key(frame, paint["id"], w, h)[:16]
        with self._lock:
            self._want[paint["id"]] = k
            if k in self._images or k in self._asked:
                return k
            self._asked.add(k)
        _DRAW.submit(self._draw, k, frame, paint["id"], w, h)
        return k

    def _draw(self, k, frame, paint_id, w, h):
        with self._lock:
            if k not in self._want.values():       # the layer changed again while this waited its turn: drawing it
                self._asked.discard(k)             # would only delay the one that is wanted (one worker, a canvas each)
                return
        try:
            image = _draw(frame, paint_id, w, h)
        except KeyError:            # the layer went (an undo) while it was being drawn: nothing to show
            image = QImage()
        with self._lock:
            self._asked.discard(k)
            if len(self._images) >= KEEP:
                self._images.pop(next(iter(self._images)))
            self._images[k], self._last[paint_id] = image, image
            self.drawn += 1
        self.notes.ready.emit()

    def picture(self, id_):
        k, _, paint_id = id_.split("?")[0].partition("/")
        with self._lock:
            got = self._images.get(k)
            return got if got is not None else self._last.get(paint_id, QImage())


def _draw(frame: dict, paint_id: str, w: int, h: int) -> QImage:
    px = np.ascontiguousarray(canvas.layer_rgba(frame, paint_id, w, h), dtype=np.uint8)
    img = QImage(px.data, w, h, 4 * w, QImage.Format.Format_RGBA8888)
    return img.scaled(SIDE, SIDE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation).copy()
