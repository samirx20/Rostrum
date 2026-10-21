"""The playhead and which stretch of the song is on screen (zoom, scroll): screen state, never an edit."""
from __future__ import annotations

from PySide6.QtCore import Property, Slot

from .signals import SoundSignals as S
from .view import STEP


class ViewSlots:
    @Property(float, notify=S.viewChanged)
    def viewStart(self):
        """The time (seconds) at the left edge of every timeline: ruler, rows, markers, playhead, piano roll."""
        return self._zoom.start

    @Property(float, notify=S.viewChanged)
    def viewSpan(self):
        """How many seconds those timelines show across their width."""
        return self._zoom.span(self._length())

    @Property(bool, notify=S.viewChanged)
    def viewFit(self):
        return self._zoom.fit

    @Slot(float)
    def setTime(self, t):
        self._t = min(max(float(t), 0.0), self._view["song"]["length"])
        self.transport.seek(self._t)
        if self._zoom.follow(self._t, self._length()):
            self.viewChanged.emit()
        self.timeChanged.emit()

    @Slot(float, float, bool, bool, float, bool, result=bool)
    def viewWheel(self, dx, dy, ctrl, shift, frac, vertical):
        """A wheel turn over a timeline. Ctrl: zoom around the pointer (`frac` across the width). Shift or a sideways
        swipe: scroll in time. A plain turn scrolls in time only when the caller has nothing to scroll up and down
        (`vertical` false). Returns false when the caller should scroll up and down."""
        if ctrl:
            self.zoomAt(STEP ** (dy / 120.0), frac)
        elif dx or shift or not vertical:
            self._zoom.scroll(-(dx or dy) / 120.0 * self.viewSpan * 0.1, self._length())
            self.viewChanged.emit()
        else:
            return False
        return True

    @Slot(float, float)
    def zoomAt(self, factor, frac):
        """Zoom in by `factor` (a pinch's scale, a wheel notch) keeping the moment at `frac` across the width."""
        self._zoom.zoom(factor, frac, self._length())
        self.viewChanged.emit()

    @Slot(float)
    def zoomStep(self, factor):
        """A key's zoom: around the playhead when it is on screen, else the middle."""
        z = self._zoom
        frac = (self._t - z.start) / z.span(self._length())
        self.zoomAt(factor, frac if 0 <= frac <= 1 else 0.5)

    @Slot()
    def fitView(self):
        self._zoom.show_all()
        self.viewChanged.emit()

    @Slot(float)
    def setViewStart(self, t):
        self._zoom.set_start(t, self._length())
        self.viewChanged.emit()

    def _moved(self, t):
        self._t = t
        if self._zoom.follow(t, self._length()):
            self.viewChanged.emit()
        self.timeChanged.emit()
