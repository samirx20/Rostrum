"""Recording on the screen: which track is armed (screen state, not a document edit), the take, and its meter.

Record starts the microphone (the engine's `record`), counts in when asked (take_clock.py), then plays the mix from
the take's start; the take lands as one `clip.add` (one undo step) placed where it was played: the part recorded
before playback was heard (the wait for the microphone and the player, the count-in) and the microphone's own
delay (when `rostrum-sound play --calibrate` measured it) are trimmed off with the clip's in-point. With punch on,
only the punch range is kept (the clip is trimmed to it) and the take stops by itself at its end. "Input level"
(record_setup.py) runs the microphone for its meter alone, before a take. What is left: the screen player's own
output delay (tens of ms); wear headphones (the speakers would also be heard by the microphone).
"""
from __future__ import annotations

import time

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from rostrum_core import RostrumError, codes
from rostrum_sound import record as rec

from .playback import SCRATCH
from .record_setup import RecordSetup
from .take_clock import TakeClock


class Recording(QObject):
    armedChanged = Signal()
    recordingChanged = Signal()
    levelChanged = Signal()

    def __init__(self, bridge, command=None, setup=None, parent=None):
        super().__init__(parent)
        self.bridge, self.command = bridge, command      # command: the test seam (see Recorder), with {out} for the take's file
        self.setup = setup or RecordSetup(bridge, self)
        self.setup.on_check = self._check
        self.clock = TakeClock(bridge, self.setup, self)
        self.clock.countChanged.connect(self.levelChanged)
        self._armed, self._rec, self._probe, self._level, self._offset = "", None, None, None, 0.0
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
        """The latest peak in dBFS while recording or checking the input; null otherwise."""
        return self._level

    @Property(float, notify=levelChanged)
    def elapsed(self):
        c = self.clock
        return time.monotonic() - c.played if self._rec and c.played is not None else 0.0

    @Property(int, notify=levelChanged)
    def counting(self):
        return self.clock.counting

    @Slot(str)
    def arm(self, track_id):
        """Arm a track (a second click disarms). Not while recording."""
        if self._rec is None:
            self._armed = "" if self._armed == track_id else track_id
            if not self._armed:
                self.setup.set("checkInput", False)
            self.setup.refresh(armed=self._armed)
            self.armedChanged.emit()

    @Slot()
    def toggleRecord(self):
        if self._rec is not None:
            self.stop()
        elif self._armed:
            self.setup.set("checkInput", False)
            self._guard(self._begin)

    def _recorder(self, out):
        return rec.Recorder(out, command=[c.replace("{out}", str(out)) for c in self.command] if self.command else None)

    def _begin(self):
        self.clock.begin()
        r = self._recorder(rec.take_path(self.bridge.doc, self._armed))
        r.start()
        self._rec, self._level, self._offset = r, -100.0, rec.input_offset(r.device)
        self.clock.start()
        self._tick.start()
        self.setup.refresh(recording=True)
        self.recordingChanged.emit()
        self.levelChanged.emit()

    def _check(self, on):
        """Input level: the microphone runs for its meter only (the file is thrown away)."""
        if on and self._probe is None and self._rec is None:
            def go():
                self._probe = self._recorder(SCRATCH / "input-check.wav")
                self._probe.start()
                self._level = -100.0
                self._tick.start()
            if not self._guard(go):
                self.setup.values["checkInput"] = False
        elif not on and self._probe is not None:
            self._probe.kill()
            self._probe, self._level = None, None
            self._tick.stop()
        self.levelChanged.emit()

    def _poll(self):
        def go():
            for _, peak in (self._rec or self._probe).poll():
                self._level = peak
            p = self.setup.punch()
            if self._rec and p and self.clock.played is not None and self.bridge.time >= p[1] + 0.05:
                self.stop()                                  # past the punch-out: the take is done
            self.levelChanged.emit()
        self._guard(go)

    @Slot()
    def stop(self):
        if self._rec is not None:
            self._guard(lambda: self._finish(self._rec.stop()))

    def _finish(self, wav):
        r, self._rec = self._rec, None
        lead = self.clock.lead + self._offset
        self._tick.stop()
        self.clock.stop()
        if r is not None:
            r.kill()
        self._level = None
        self.setup.refresh(recording=False)
        self.recordingChanged.emit()
        self.levelChanged.emit()
        if wav is not None:
            p = self.setup.punch()
            call = rec.place_take(self._armed, wav, self.clock.at, float(r.done["seconds"]), lead, p)
            if call is None:
                raise RostrumError(codes.BAD_ARGUMENT, "record", "the punch range",
                                   f"was never reached: the take ran from {self.clock.at:.2f} s, the range is "
                                   f"{p[0]:.2f}–{p[1]:.2f} s", [], "Start before the punch-out and play into the range.")
            self.bridge._apply([call], "Record take")

    def _guard(self, fn) -> bool:
        try:
            fn()
            return True
        except RostrumError as e:
            if self._rec is not None:
                self._finish(None)
            if self._probe is not None:
                self._check(False)
            self.bridge._fail(e.line())
            return False

    def close(self):
        self._check(False)
        if self._rec is not None:
            self._finish(None)
