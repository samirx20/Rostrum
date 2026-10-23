"""The paint layer list's thumbnails (painting design §2.3, mockup paint-02): each paint layer's own pixels, small, see-through
(image://paintthumbs/<key>; PaintOn.qml lays them on mid-grey squares, so ink of any colour reads). Drawn by the painting kit (`canvas.layer_rgba`, the same pixels a render
uses) on the GUI thread when the list asks, kept per layer content, so a layer is drawn again only after it changed.
"""
from __future__ import annotations

import hashlib
import json
import threading

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider
from rostrum_paint import canvas

SIDE = 48          # px: twice the row's thumbnail box, so it stays sharp on a high-density screen
KEEP = 64


class ThumbProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._lock, self._images = threading.Lock(), {}

    def key(self, frame: dict, paint: dict, w: int, h: int) -> str:
        """The thumbnail's name for this layer's content, drawn now when it isn't kept yet."""
        k = hashlib.sha1(json.dumps([frame.get("paintmasks", []), paint["strokes"], w, h], sort_keys=True,
                                    default=str).encode()).hexdigest()[:16]
        with self._lock:
            if k in self._images:
                return k
        image = _draw(frame, paint["id"], w, h)
        with self._lock:
            if len(self._images) >= KEEP:
                self._images.pop(next(iter(self._images)))
            self._images[k] = image
        return k

    def requestImage(self, id_, size, requested):  # noqa: N802 (Qt's name)
        with self._lock:
            return self._images.get(id_.split("?")[0], QImage())


def _draw(frame: dict, paint_id: str, w: int, h: int) -> QImage:
    px = np.ascontiguousarray(canvas.layer_rgba(frame, paint_id, w, h), dtype=np.uint8)
    img = QImage(px.data, w, h, 4 * w, QImage.Format.Format_RGBA8888)
    return img.scaled(SIDE, SIDE, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation).copy()
