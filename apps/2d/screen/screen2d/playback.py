"""Playing the canvas (the bridge's `play`).

Playback follows the clock: each tick puts the playhead where real time says and draws that frame; frames that
couldn't be drawn in time are skipped, so motion plays at its true speed. While playing only the playhead and the
frame change; the inspector, layer outline and handles catch up when it stops (they cost more than a frame).

Motion blur draws each frame several times (the composition's Blur steps). With "Blur while playing" off (the
default), playback asks the engine for one step per frame (its `shutterSamples` override), the same scene and the
same engine, so it keeps up; a paused frame and every export are the full picture.

"Preview size" (Full, the default, Half or Quarter) draws playing frames smaller (the engine's `scale`: the same
scene, drawn through a view scale, so nothing moves); the canvas stretches them to fit. It is offered only for a
composition at least SIZE_FROM px on its long side, where a full frame can cost more than a frame's time; a smaller
one plays at full size. A paused frame is always full size: what you judge is what exports.
"""
from __future__ import annotations

import time

from PySide6.QtCore import Property, QObject, Qt, QTimer, Signal, Slot

from .playstats import STATS

SIZES = {"full": 1.0, "half": 0.5, "quarter": 0.25}   # Preview size → the engine's `scale`
SIZE_FROM = 1280                                      # px on the long side from which Preview size is offered


def size_offered(comp: dict) -> bool:
    """Preview size matters (is shown and used) for this composition."""
    return max(comp["width"], comp["height"]) >= SIZE_FROM


class Playback(QObject):
    changed = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b, self._clock, self._blur, self._size = bridge, (0.0, 0.0), False, "full"
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)

    @Property(bool, notify=changed)
    def playing(self):
        return self._timer.isActive()

    @Property(bool, notify=changed)
    def blur(self):
        """Full motion blur while playing (slower), or one blur step per frame (keeps up)."""
        return self._blur

    @Slot(bool)
    def setBlur(self, on):
        self._blur = bool(on)
        self.changed.emit()

    @Property(str, notify=changed)
    def size(self):
        """Preview size while playing: full, half or quarter."""
        return self._size

    @Slot(str)
    def setSize(self, size):
        if size not in SIZES:
            raise ValueError(f"Preview size is one of {', '.join(SIZES)}; got {size!r}")
        self._size = size
        self.changed.emit()

    @Slot()
    def toggle(self):
        if self._timer.isActive():
            self.stop()
            self.b.setTime(self.b.time)        # the rest of the screen catches up; the full frame is drawn
        else:
            self._clock = (time.perf_counter(), self.b.time)
            self._timer.start(max(1, round(1000 / self.b.comp()["fps"])))
            self.changed.emit()

    def stop(self):
        if self._timer.isActive():
            self._timer.stop()
            self.changed.emit()

    def samples(self) -> int | None:
        """Motion-blur steps for the frame being asked for: 1 while playing without blur, else the composition's."""
        return 1 if self._timer.isActive() and not self._blur else None

    def scale(self) -> float:
        """The engine's `scale` for the frame being asked for: Preview size while playing (where it is offered), else 1."""
        if not self._timer.isActive() or not size_offered(self.b.comp()):
            return 1.0
        return SIZES[self._size]

    def _tick(self):
        c = self.b.comp()
        t = self._clock[1] + time.perf_counter() - self._clock[0]
        if t > c["duration"] + 1e-9:            # loop
            self._clock, t = (time.perf_counter(), 0.0), 0.0
        with STATS.stage("gui"):
            self.b.setTime(t)
