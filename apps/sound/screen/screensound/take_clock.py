"""The start of a take, shared by microphone and keyboard takes: the count-in clicks, then playback from the take's
start, and how much of the input came before the moment playback was heard (`lead`), so the take is placed where it
was played. The input (microphone or keyboard) starts first and says when it is ready; playback starts after the
count-in, once the screen's player actually plays (it may wait for a render). Screen playback is Qt's player, so
what is left is its output delay (a few tens of ms); headphones keep the speakers out of a microphone take.
"""
from __future__ import annotations

import time

import numpy as np
import soundfile as sf
from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal

from .playback import SCRATCH


def _click_file():
    f = SCRATCH / "count-in-click.wav"
    if not f.is_file():
        t = np.arange(int(48000 * 0.03)) / 48000
        sf.write(f, (np.sin(2 * np.pi * 1500 * t) * np.exp(-t * 160) * 0.8).astype("float32"), 48000)
    return f


class TakeClock(QObject):
    countChanged = Signal()

    def __init__(self, bridge, setup, parent=None):
        super().__init__(parent)
        self.bridge, self.setup = bridge, setup
        self.at, self.ready, self.played, self._left, self._per_bar, self._started_play = 0.0, 0.0, None, 0, 4, False
        self._beat = QTimer(self, timeout=self._click)
        self._sound, self._connected = None, False

    @Property(int, notify=countChanged)
    def counting(self):
        """Count-in clicks still to come (0 = none, or the take is running)."""
        return self._left

    def begin(self):
        """Before the input starts: move the playhead to where this take starts playing."""
        if not self.bridge.playing:
            t = self.setup.start_at(self.bridge.time)
            if abs(t - self.bridge.time) > 1e-6:
                self.bridge.setTime(t)

    def start(self):
        """The input is ready now: count in, then play. `at` is the timeline time the take starts from."""
        self.ready, self.played, self.at = time.monotonic(), None, self.bridge.time
        self._started_play = False
        clicks, beat = (0, 0) if self.bridge.playing else self.setup.count_in(self.at)
        if self.bridge.playing:
            self.played = self.ready                         # already playing: the input runs along from here
        elif clicks:
            self._left, self._per_bar = clicks, int(self.bridge.doc.data.get("beatsPerBar", 4))
            self._beat.setInterval(round(beat * 1000))
            self._click()
            self._beat.start()
        else:
            self._play()
        self.countChanged.emit()

    def _click(self):
        if self._left <= 0:
            self._beat.stop()
            self._play()
            return
        if self._sound is None:
            from PySide6.QtMultimedia import QSoundEffect
            self._sound = QSoundEffect(self)
            self._sound.setSource(QUrl.fromLocalFile(str(_click_file())))
        self._sound.setVolume(1.0 if self._left % self._per_bar == 0 else 0.55)    # the bar's first beat louder
        self._sound.play()
        self._left -= 1
        self.countChanged.emit()

    def _play(self):
        self._left = 0
        if not self._connected:
            self.bridge.transport.playingChanged.connect(self._heard)
            self._connected = True
        self._started_play = True
        self.bridge.togglePlay()
        self._heard()
        self.countChanged.emit()

    def _heard(self):
        if self.played is None and self.bridge.playing:
            self.played = time.monotonic()

    @property
    def lead(self) -> float:
        """Seconds of input before the take's start was heard (the count-in and the wait for playback)."""
        return (self.played if self.played is not None else time.monotonic()) - self.ready

    def stop(self):
        self._beat.stop()
        self._left = 0
        if self._connected:
            self.bridge.transport.playingChanged.disconnect(self._heard)
            self._connected = False
        if self._started_play and self.bridge.playing:
            self.bridge.togglePlay()
        self._started_play = False
        self.countChanged.emit()
