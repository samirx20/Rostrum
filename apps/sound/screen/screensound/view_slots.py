"""The playhead and which stretch of the song is on screen (zoom, scroll): screen state, never an edit. The view itself
is the kit's `TimeView` (`backend.timeView`, a `TimeViewObject`: HScroll binds to it); these slots are Sound's names for
it, and the playhead's page-follow."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Slot
from rostrum_sound.doc import musical

from .signals import SoundSignals as S


class ViewSlots:
    timeView = Property(QObject, lambda self: self._tv, constant=True)     # HScroll's view

    @Slot(float, "QVariant", result=str)
    def positionText(self, t, _song=None):
        """A time as people read it: bars.beats, then the clock ("5.3  0:09.60"), from the one formatter (musical.py)
        that every field and agent report uses; the ticks are left off here. QML passes `backend.song` so the text
        follows a tempo or time signature edit, not only the playhead."""
        return ".".join(musical.position(t, self.doc.data).split(".")[:2]) + "  " + musical.clock(t)

    @Slot(str, result=str)
    def jumpTo(self, text):
        """The position field: typed bars.beats ("5.3", "5.3.480"), a clock ("0:09.6") or seconds ("9.6 s") moves the playhead
        there (the one parser, musical.py). "" when it did; else the refusal, in words, for the field to show."""
        try:
            t = musical.parse(text.split("  ")[0], self.doc.data)
        except ValueError as e:
            return str(e)
        if t > self._view["song"]["length"] + 1e-6:
            return f"The song is {musical.clock(self._view['song']['length'])} long: {musical.clock(t)} is past its end"
        self.setTime(t)
        return ""

    @Property(float, notify=S.viewChanged)
    def viewStart(self):
        """The time (seconds) at the left edge of every timeline: ruler, rows, markers, playhead, piano roll."""
        return self._zoom.start

    @Property(float, notify=S.viewChanged)
    def viewSpan(self):
        """How many seconds those timelines show across their width."""
        return self._zoom.span

    @Property(bool, notify=S.viewChanged)
    def viewFit(self):
        return self._zoom.fit

    @Slot(float)
    def setTime(self, t):
        self._t = min(max(float(t), 0.0), self._view["song"]["length"])
        self.transport.seek(self._t)
        self._tv.follow(self._t)
        self.timeChanged.emit()

    @Slot(float, float, bool, bool, float, bool, result=bool)
    def viewWheel(self, dx, dy, ctrl, shift, frac, vertical):
        """A wheel turn over a timeline (kit TimeView.wheel). False: the caller should scroll up and down."""
        return self._tv.wheel(dx, dy, ctrl, shift, frac, vertical)

    @Slot(float, float)
    def zoomAt(self, factor, frac):
        """Zoom in by `factor` (a pinch's scale, a wheel notch) keeping the moment at `frac` across the width."""
        self._tv.zoomAt(factor, frac)

    @Slot(float)
    def zoomStep(self, factor):
        """A key's zoom: around the playhead when it is on screen, else the middle."""
        self._tv.zoomStep(factor, self._t)

    @Slot()
    def fitView(self):
        self._tv.showAll()

    @Slot(float)
    def setViewStart(self, t):
        self._tv.setStart(t)

    def _moved(self, t):
        self._t = t
        self._tv.follow(t)
        self.timeChanged.emit()
