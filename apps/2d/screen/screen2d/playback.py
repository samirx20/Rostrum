"""Playing the canvas (the bridge's `play`).

Playback follows the clock: each tick puts the playhead where real time says and draws that frame; frames that
couldn't be drawn in time are skipped, so motion plays at its true speed. While playing only the playhead and the
frame change, together: the playhead moves when the picture of its time arrives (bridge2d `_picture_arrives`), so a
frame costs the window one redraw and the playhead never runs ahead of the picture. The inspector, layer outline and
handles catch up when it stops (they cost more than a frame).

Scrubbing (the playhead moved by hand while paused, a move within SETTLE_MS of the one before: the ruler dragged, a
key held) is time moving too: its pictures are drawn the way playing draws them (one blur step unless "Motion blur
while playing" is on; the world picture at half size, world_view.py, as during a canvas drag) and the panels wait.
SETTLE_MS after the last move the playhead rests: the full frame is drawn and the panels follow. One jump or step
of the playhead is not a scrub: it is drawn full at once.

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

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from .frame_clock import FrameClock
from .playstats import STATS

SIZES = {"full": 1.0, "half": 0.5, "quarter": 0.25}   # Preview size → the engine's `scale`
SIZE_FROM = 1280                                      # px on the long side from which Preview size is offered
TICK_MS = 4                                           # the playing clock's tick (_tick_ms)
SETTLE_MS = 120                                       # a scrub rests this long after its last move (a few frames)


def size_offered(comp: dict) -> bool:
    """Preview size matters (is shown and used) for this composition."""
    return max(comp["width"], comp["height"]) >= SIZE_FROM


class Playback(QObject):
    changed = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b, self._clock, self._blur, self._size = bridge, (0.0, 0.0), False, "full"
        self._once = None                                   # (until, back to): playing a stretch once (once())
        self._timer = FrameClock(self)                      # ticks on time where a Qt timer can't (frame_clock.py)
        self._timer.timeout.connect(self._tick)
        self.scrubbing, self._moved_at = False, 0.0         # the playhead moved by hand, and when last
        self.quick = False                                  # a hand move's quick picture is due (until it rests)
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(SETTLE_MS)
        self._settle.timeout.connect(self._rest)

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

    def moved_by_hand(self) -> bool:
        """The playhead was moved while paused (bridge.setTime): a scrub when within SETTLE_MS of the move before (its
        picture drawn as playing draws, the panels wait); the rest follows SETTLE_MS after the last move."""
        now = time.perf_counter()
        self.scrubbing = now - self._moved_at < SETTLE_MS / 1000
        self._moved_at = now
        self.quick = True                       # every move by hand, a ruler click too: the quick picture at once (half
        self._settle.start()                    # size, one blur step), sharpened in place SETTLE_MS later (PLAN D2)
        return self.scrubbing

    def _rest(self):
        self.quick = False
        if self.scrubbing:
            self.scrubbing = False
            self.b.time_rests()
        else:
            self.b._show()                      # a single move: its panels followed at once; the sharp picture now

    def moving(self) -> bool:
        """Time is moving: playing, or a scrub."""
        return self._timer.isActive() or self.scrubbing or self.quick

    @Slot()
    def toggle(self):
        if self._timer.isActive():
            self.stop()
            self.b.setTime(self.b.time)        # the rest of the screen catches up; the full frame is drawn
        else:
            self.scrubbing = self.quick = False
            self._settle.stop()
            self._clock = (time.perf_counter(), self.b.time)
            self._timer.start(self._tick_ms())
            self.b.soundtrack.play(self.b.time)     # the project's sound, through Sound's engine (soundtrack.py)
            self.changed.emit()

    def once(self, t0: float, t1: float, back: float):
        """Play t0 → t1 once, then stop with the playhead back at `back` (ease_play.py: an ease picked plays once)."""
        self.stop()
        self._once = (t1, back)
        self.b.setTime(t0)
        self._clock = (time.perf_counter(), self.b.time)
        self._timer.start(self._tick_ms())
        self.changed.emit()

    def stop(self):
        self._once = None                       # stopped by hand: it stays where it is
        self.b.soundtrack.stop()
        if self._timer.isActive():
            self._timer.stop()
            self.changed.emit()

    def samples(self) -> int | None:
        """Motion-blur steps for the frame being asked for: 1 while time moves (playing, scrubbing) without "Motion blur
        while playing", else the composition's."""
        return 1 if self.moving() and not self._blur else None

    def scale(self) -> float:
        """The engine's `scale` for the frame being asked for: Preview size while playing (where it is offered), else 1."""
        if not self._timer.isActive() or not size_offered(self.b.comp()):
            return 1.0
        return SIZES[self._size]

    def _tick_ms(self) -> int:
        """Ticks every TICK_MS (or twice the frame rate, if faster): each new frame is asked within a few ms of its time.
        Ticks at the frame rate, or twice it, beat against the screen's refresh: at 25 fps on a 60 Hz screen pictures
        stayed up anywhere from 1 to 4 refreshes instead of 2 or 3. A tick on the frame shown does nothing."""
        return max(1, min(TICK_MS, round(500 / self.b.comp()["fps"])))

    def ahead(self, t: float) -> float | None:
        """While playing, the frame after `t` (bridge.setTime's own rounding, so the next tick asks for exactly it): asked
        with `t`, the engine draws it while `t` is shown. None paused or at the end."""
        if not self._timer.isActive():
            return None
        c = self.b.comp()
        nxt = round((t + 1 / c["fps"]) * c["fps"]) / c["fps"]
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
