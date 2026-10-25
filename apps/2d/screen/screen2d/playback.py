"""Playing the canvas (the bridge's `play`).

Playback follows the clock: each tick puts the playhead where real time says and draws that frame; frames that
couldn't be drawn in time are skipped, so motion plays at its true speed. While playing only the playhead and the
frame change; the inspector, layer outline and handles catch up when it stops (they cost more than a frame).

Motion blur draws each frame several times (the composition's Blur steps). With "Motion blur while playing" off (a checked entry in the canvas view menu) (the
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
        self._once = None                                   # (until, back to): playing a stretch once (once())
        self._asked, self._step = None, 1.0                 # (frame asked last, when) and the frames a picture takes (ahead())
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
            self._clock, self._asked = (time.perf_counter(), self.b.time), None
            self._timer.start(self._tick_ms())
            self.b.soundtrack.play(self.b.time)     # the project's sound, through Sound's engine (soundtrack.py)
            self.changed.emit()

    def once(self, t0: float, t1: float, back: float):
        """Play t0 → t1 once, then stop with the playhead back at `back` (ease_play.py: an ease picked plays once)."""
        self.stop()
        self._once = (t1, back)
        self.b.setTime(t0)
        self._clock, self._asked = (time.perf_counter(), self.b.time), None
        self._timer.start(self._tick_ms())
        self.changed.emit()

    def stop(self):
        self._once = None                       # stopped by hand: it stays where it is
        self.b.soundtrack.stop()
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

    def _tick_ms(self) -> int:
        """Ticks at twice the frame rate: each new frame is caught within half a frame (ticks at the frame rate drift
        against the frames, skipping one now and then); a tick on the frame shown does nothing."""
        return max(1, round(500 / self.b.comp()["fps"]))

    def ahead(self, t: float) -> float | None:
        """While playing, the frame the next tick will really ask for (bridge.setTime's own rounding): `t` plus the
        frames one picture takes to come, at least one (the time between asks, smoothed so one late tick doesn't move
        it), so a picture that takes longer than a frame still finds the one drawn ahead ready (asking t + 1 then made
        the engine drop it: blur at 60 fps fell to 25 fps). Asked with `t`, the engine draws it while `t` is shown.
        None paused or at the end."""
        if not self._timer.isActive():
            self._asked = None
            return None
        c = self.b.comp()
        n, now = round(t * c["fps"]), time.perf_counter()
        if self._asked is None or n < self._asked[0]:          # a start, or a loop back to 0
            self._asked, self._step = (n, now), 1.0
        elif n > self._asked[0]:
            gap = (now - self._asked[1]) * c["fps"]            # frames of the clock between the two asks
            self._asked, self._step = (n, now), 0.7 * self._step + 0.3 * gap
        nxt = (n + max(1, round(self._step))) / c["fps"]      # = round(nxt * fps) / fps, as setTime rounds
        return nxt if nxt <= c["duration"] else None

    def _tick(self):
        c = self.b.comp()
        t = self._clock[1] + time.perf_counter() - self._clock[0]
        heard = self.b.soundtrack.heard()       # while the mix rolls the picture follows the speaker, else its clock
        if heard is not None and heard <= c["duration"]:
            self._clock, t = (time.perf_counter(), heard), heard
        if self._once is not None and t > self._once[0] + 1e-9:      # a stretch played once: back where it was
            back, self._once = self._once[1], None
            self._timer.stop()
            self.changed.emit()
            self.b.setTime(back)
            return
        if t > c["duration"] + 1e-9:            # loop
            self._clock, t = (time.perf_counter(), 0.0), 0.0
            self.b.soundtrack.play(0.0)
        if round(t * c["fps"]) == round(self.b.time * c["fps"]):
            return                              # still the frame shown (ticks are a little faster than frames): nothing new
        with STATS.stage("gui"):
            self.b.setTime(t)
