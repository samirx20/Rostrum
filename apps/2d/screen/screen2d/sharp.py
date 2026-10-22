"""Sharp zoom: past Full (more device px than composition px), the canvas's frame is the full-size picture enlarged, so
each frame job also asks the engine for the visible part drawn again at the size shown (frames.py `crop`, the
engine's `frame` `view`: the same paint as any frame and the export, never a preview-only drawing). The crop lies over
the frame where it belongs (Stage.qml, image://framecrop/<n>); while the view moves, the enlarged frame and the last
crop show until the new crop arrives (asked once the view has settled; newest request wins).
No crop while playing or dragging (speed first), nor at or below Full. A QObject part, read in QML as `backend.sharp`.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

MOST_SCALE = 64.0          # the canvas's top zoom; the engine's limit too
MOST_PX = 8192             # the engine's largest picture side


class Sharp(QObject):
    changed = Signal()

    def __init__(self, bridge, frames):
        super().__init__(bridge)
        self.b = bridge
        self._visible = None        # (x0, y0, x1, y1) comp px of the well, from Stage.qml
        self._ratio = 1.0           # device px per screen px
        self._asked = None          # the crop the last job asked for
        self._shown = {}            # the crop on screen: {serial, x, y, w, h}
        frames.cropped.connect(self._on_cropped)

    @Slot(float, float, float, float, float)
    def setVisible(self, x0, y0, x1, y1, device_ratio):
        """The view settled (Stage.qml): the well shows comp px x0..x1, y0..y1. A different crop is drawn now."""
        self._visible, self._ratio = (x0, y0, x1, y1), max(float(device_ratio), 1.0)
        if self.crop() != self._asked:
            self.b._show()

    def crop(self) -> dict | None:
        """The crop the next frame job asks for: the visible part of the composition at the device px it is shown at."""
        k = self.b.view_zoom() * self._ratio
        if self._visible is None or k <= 1.001 or self.b.play.playing or self.b.dragging():
            return None
        info = self.b.comp()
        x0, y0, x1, y1 = self._visible
        x0, y0 = max(0, int(x0)), max(0, int(y0))                       # whole comp px, inside the frame
        x1, y1 = min(info["width"], int(x1) + 1), min(info["height"], int(y1) + 1)
        k = min(k, MOST_SCALE, MOST_PX / max(x1 - x0, y1 - y0, 1))
        if x1 <= x0 or y1 <= y0:
            return None
        return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "scale": round(k, 4)}

    def asked(self, crop):
        """A frame job with this crop (None: none) was just requested."""
        self._asked = crop
        if crop is None and self._shown:
            self._shown = {}
            self.changed.emit()

    def _on_cropped(self, serial, rect):
        self._shown = {"serial": serial, **{k: rect[k] for k in ("x", "y", "w", "h")}} if serial else {}
        self.changed.emit()

    @Property("QVariantMap", notify=changed)
    def picture(self):
        """The sharp crop on screen ({} for none): `serial` for image://framecrop, its comp px rect x, y, w, h."""
        return self._shown
