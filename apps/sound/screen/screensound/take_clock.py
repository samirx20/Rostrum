"""The start and end of a take, shared by microphone and keyboard takes, on the engine's live transport
(live_transport.py): the count-in is the engine's own ({"countIn"}: its clicks, then the mix rolls on the frame), the
recording is armed there ({"record": true}, or with the punch range), and the engine places what it records at the
mix time heard with it. So nothing is guessed here: no clicks of our own, no timing of when playback was heard.
"""
from __future__ import annotations

import math
import time

from PySide6.QtCore import Property, QObject, Signal
from rostrum_sound.doc import tempo


class TakeClock(QObject):
    countChanged = Signal()

    def __init__(self, bridge, setup, parent=None):
        super().__init__(parent)
        self.bridge, self.setup = bridge, setup
        self.player = bridge.transport.player
        self.at, self._beats, self._t0, self._started_play = 0.0, 0, 0.0, False

    @Property(int, notify=countChanged)
    def counting(self):
        """Count-in clicks still to come (0 = none, or the mix is rolling)."""
        if not self._beats or self.player.rolled or not self.player.playing:
            return 0
        beat = tempo.beat_seconds(self.bridge.doc.data, self.at)
        return max(0, min(self._beats, math.ceil(self._beats - (time.monotonic() - self._t0) / beat)))

    def start_time(self) -> float:
        """Where the take starts playing: the playhead, or a bar before the punch-in when it is past it."""
        return self.bridge.time if self.bridge.playing else self.setup.start_at(self.bridge.time)

    def begin(self):
        """Arm the engine's recording (with the punch), set its count-in, and play from the take's start."""
        p = self.setup.punch()
        playing = self.bridge.playing
        self.at = self.start_time()
        beats, _ = self.setup.count_in(self.at)
        self._beats = 0 if playing else beats
        self.player.set_state(countIn=self.setup.values["countInBars"] if self._beats else 0,
                              record={"punch": [p[0], p[1]]} if p else True)
        self._started_play = not playing
        if not playing:
            if abs(self.at - self.bridge.time) > 1e-6:
                self.bridge.setTime(self.at)
            self._t0 = time.monotonic()
            self.bridge.togglePlay()
        self.countChanged.emit()

    def stop(self):
        """End the take: the engine writes what it recorded ({"take"} / {"note"}), then the recording is disarmed."""
        if self._started_play and self.bridge.playing:
            self.bridge.togglePlay()
        self.player.set_state(record=False, countIn=0)
        self._started_play, self._beats = False, 0
        self.countChanged.emit()
