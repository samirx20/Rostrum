"""Frames drawn ahead for a scrub (PLAN D2, After Effects' cached frames): while nothing else is going on (paused,
not dragging, not scrubbing, the picture of the state shown landed), the canvas's engine draws the quick pictures a
scrub asks for (half size, one blur step: playback.py, world_view.quick_rect) one frame at a time, nearest the
playhead first, into frames.py's QuickCache. A scrub or a ruler click over them then shows its picture in the frame
of the move; elsewhere it shows the quick picture as soon as the engine draws it. Each fill waits behind any
picture asked for, so a scrub is held by one quick picture at most. `ready` (the frame times drawn, for the view as
it is) is what the time ruler's thin ready line shows (ReadyLine.qml). A QObject part, read in QML as
`backend.scrubAhead`.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal

IDLE_MS = 300            # quiet this long after the last picture landed before drawing ahead


class ScrubAhead(QObject):
    changed = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b = bridge
        self._busy = False               # a fill is with the engine
        self._ready: list[float] = []
        self._soon = QTimer(self)
        self._soon.setSingleShot(True)
        self._soon.setInterval(IDLE_MS)
        self._soon.timeout.connect(self._next)
        bridge.frames.filled.connect(self._filled)
        bridge.frameChanged.connect(self._soon.start)       # a picture landed: draw ahead once things are quiet

    @Property("QVariantList", notify=changed)
    def ready(self):
        """Times (composition seconds) whose quick picture is drawn for the view as it is."""
        return self._ready

    def _target(self):
        """(scene, quick rect) to draw ahead for now, or None when this is no time for it."""
        b = self.b      # (paint-on pictures still being made: their frames would show stand-ins, and drawing them slowed
        #                  the making ~3×, 2D final critic)
        if self._busy or not b._scene or b._waiting is not None or b._ahead is not None or b.play.playing or b.play.moving() or b.dragging():
            return None
        world = b._world.quick_rect()
        return None if world is None else (b._scene, world)

    def _tell(self, scene, world):
        got = self.b.frames.quick.times(scene, world)
        if got != self._ready:
            self._ready = got
            self.changed.emit()

    def _next(self):
        target = self._target()
        if target is None:
            if not self._busy and self.b.play.moving():
                self._soon.start()                           # a scrub is on: after it rests
            return
        scene, world = target
        self._tell(scene, world)
        if self.b.frames.quick.full():
            return
        c = self.b.comp()
        fps, n = float(c["fps"]), int(round(c["duration"] * c["fps"]))
        done = set(self._ready)
        now = round(self.b.time * fps)
        todo = sorted((f for f in range(n + 1) if round(f / fps, 4) not in done), key=lambda f: (abs(f - now), f))
        if not todo:
            return
        self._busy = True
        self.b.frames.fill(scene, round(todo[0] / fps, 4), world)

    def _filled(self, scene, t, room):
        self._busy = False
        if scene is self.b._scene:
            world = self.b._world.quick_rect()
            if world is not None:
                self._tell(scene, world)
        if room:
            QTimer.singleShot(0, self._next)                # the next one, unless something else came meanwhile
