"""The world picture the canvas shows (camera spec § 3.1, 8.4, 5 #29): the engine draws the world rectangle the view
shows, a margin around it, at the size shown (up to 64 ×, 8192 px a side), the frame's quad holding the export (the
engine's `frame` `world`: the same paint as the export, never a preview-only drawing). Stage.qml lays the picture at
its world rectangle through the one view mapping, so panning moves the picture at once and a new one is asked only
when the view leaves what it covers or the size shown changes (newest request wins). Playing asks no world: the canvas
looks through the frame (spec § 4.8), the export fitted in the well.

`rect()` is the world rectangle the next frame job asks for. The pictures drawn last are kept (frames.py
`WorldCache`), so panning back, fitting back or scrubbing back over the same view shows them without the engine.
A QObject part, read in QML as `backend.world`.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Property, QObject, Signal, Slot

MOST_SCALE = 64.0          # the engine's limits
MOST_PX = 8192
MARGIN = 0.25              # of the visible size, each side: room to pan before a new picture is needed
DRAG_SCALE = 0.5           # while dragging or scrubbing (playback.py): the picture at half the size shown, so it keeps up


def on_pixels(x: float, y: float, w: float, h: float, k: float) -> dict:
    """The world rectangle round x, y, w, h whose edges fall on whole picture px at `k` px per world px: the engine's
    picture (round(w · k) px wide) then lands on the screen's px with no resampling (the view's origin is on a whole
    device px too: CanvasView.qml), so at 100 % the canvas is the export px for px."""
    px0, py0 = math.floor(x * k), math.floor(y * k)
    pw, ph = math.ceil((x + w) * k) - px0, math.ceil((y + h) * k) - py0
    return {"x": px0 / k, "y": py0 / k, "w": pw / k, "h": ph / k, "scale": k}


class WorldView(QObject):
    changed = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b = bridge
        self._visible = None        # (x0, y0, x1, y1) world px of the well, from Stage.qml
        self._ratio = 1.0           # device px per screen px
        self._shown = {}            # the picture on screen: {serial, x, y, w, h, world: bool}
        self._covers = None         # the world rect + scale of the newest asked picture

    @Slot(float, float, float, float, float)
    def setVisible(self, x0, y0, x1, y1, device_ratio):
        """The view moved (Stage.qml): the well shows world px x0..x1, y0..y1. A new picture is asked only when the
        last one no longer covers it at the size shown."""
        self._visible, self._ratio = (x0, y0, x1, y1), max(float(device_ratio), 1.0)
        if self.rect() != self._covers:
            self.b._show()

    def scale(self) -> float:
        """Device px per world px for the next picture."""
        k = self.b.view_zoom() * self._ratio
        moving = self.b.dragging() or self.b.play.scrubbing
        return k * DRAG_SCALE if moving and not self.b.play.playing else k

    def rect(self) -> dict | None:
        """The world rectangle the next frame job asks for (None while playing or before the view is known): the
        last one while it still covers the view at the same size, else the view with a margin round it."""
        if self._visible is None or self.b.play.playing:
            return None
        x0, y0, x1, y1 = self._visible
        k = round(min(self.scale(), MOST_SCALE), 4)
        last = self._covers
        if last and last["scale"] == k and last["x"] <= x0 and last["y"] <= y0 \
                and last["x"] + last["w"] >= x1 and last["y"] + last["h"] >= y1:
            return last
        w, h = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
        mx, my = w * MARGIN, h * MARGIN
        w, h = w + 2 * mx, h + 2 * my
        k = round(min(k, (MOST_PX - 2) / w, (MOST_PX - 2) / h), 4)     # 2 px spare: on_pixels rounds out
        return on_pixels(x0 - mx, y0 - my, w, h, k)

    def asked(self, rect):
        """A frame job with this world rect (None: the export, playing) was just requested."""
        self._covers = rect

    def shown(self, serial: int, rect: dict | None):
        """The picture `serial` (drawn for `rect`, or the export when None) is on screen now."""
        self._shown = {"serial": serial, "world": rect is not None, **({k: rect[k] for k in ("x", "y", "w", "h")} if rect else {})}
        self.changed.emit()

    def visible(self) -> dict | None:
        """The part of the world the canvas shows, or None (the agents' view state, screen_seen.py)."""
        v = self._visible
        return None if v is None else {"x": v[0], "y": v[1], "w": v[2] - v[0], "h": v[3] - v[1]}

    @Property("QVariantMap", notify=changed)
    def picture(self):
        """The picture on screen: `serial` (image://frame), `world` and its world px rect x, y, w, h (a world
        picture), or the export (world false: playing, fitted in the well)."""
        return self._shown
