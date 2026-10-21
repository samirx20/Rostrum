"""Recording on the screen: which track is armed (screen state, not a document edit), the take, and its meter.

Record plays the mix from the playhead (the screen's own playback) while the engine's `record` listens to the
microphone; the take lands as one `clip.add` (one undo step) at the playhead where recording started. Caveat: the
microphone and the speakers each have a little delay (tens of ms), so a take made against playback sits slightly
late; wear headphones (the speakers would also be heard by the microphone). The engine's transport can
overdub with exact timing, but it is not reachable from `serve` yet.
"""
from __future__ import annotations

import time

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from rostrum_core import RostrumError
from rostrum_sound import record as rec


class Recording(QObject):
    armedChanged = Signal()
    recordingChanged = Signal()
    levelChanged = Signal()

    def __init__(self, bridge, command=None, parent=None):
        super().__init__(parent)
        self.bridge, self.command = bridge, command      # command: the test seam (see Recorder), with {out} for the take's file
        self._armed, self._rec, self._at, self._level, self._began = "", None, 0.0, None, 0.0
        self._started_play = False
        self._tick = QTimer(self, interval=50, timeout=self._poll)

    @Property(str, notify=armedChanged)
    def armed(self):
        """The armed track's id ("" when none)."""
        return self._armed

    @Property(bool, notify=recordingChanged)
    def recording(self):
        return self._rec is not None

    @Property("QVariant", notify=levelChanged)
    def level(self):
        """The latest peak in dBFS while recording; null when not recording."""
        return self._level

    @Property(float, notify=levelChanged)
    def elapsed(self):
        return time.monotonic() - self._began if self._rec else 0.0

    @Slot(str)
    def arm(self, track_id):
        """Arm a track (a second click disarms). Not while recording."""
        if self._rec is None:
            self._armed = "" if self._armed == track_id else track_id
            self.armedChanged.emit()

    @Slot()
    def toggleRecord(self):
        if self._rec is not None:
            self.stop()
        elif self._armed:
            self._guard(self._begin)

    def _begin(self):
        out = rec.take_path(self.bridge.doc, self._armed)
        r = rec.Recorder(out, command=[c.replace("{out}", str(out)) for c in self.command] if self.command else None)
        r.start()
        self._rec, self._at, self._began, self._level = r, self.bridge.time, time.monotonic(), -100.0
        self._started_play = not self.bridge.playing
        if self._started_play:
            self.bridge.togglePlay()
        self._tick.start()
        self.recordingChanged.emit()
        self.levelChanged.emit()

    def _poll(self):
        def go():
            for _, peak in self._rec.poll():
                self._level = peak
            self.levelChanged.emit()
        self._guard(go)

    @Slot()
    def stop(self):
        if self._rec is not None:
            self._guard(lambda: self._finish(self._rec.stop()))

    def _finish(self, wav):
        r, self._rec = self._rec, None
        self._tick.stop()
        if r is not None:
            r.kill()
        if self._started_play and self.bridge.playing:
            self.bridge.togglePlay()
        self._level = None
        if wav is not None:
            self.bridge._apply([rec.take_call(self._armed, wav, round(self._at, 3))], "Record take")
        self.recordingChanged.emit()
        self.levelChanged.emit()

    def _guard(self, fn) -> bool:
        try:
            fn()
            return True
        except RostrumError as e:
            if self._rec is not None:
                self._finish(None)
            self.bridge._fail(e.line())
            return False

    def close(self):
        if self._rec is not None:
            self._finish(None)
