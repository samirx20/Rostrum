"""Work that may show one frame after the pointer's own: `AfterFrame(fn).ask()` runs `fn` once, right after the next
frame of the app's window is on screen (its frameSwapped), so what the click itself changes (a row lit, an outline)
is drawn first and the rest (a pick's settings panel) lands in the frame after, instead of both waiting for each
other. A second ask before it ran is the same run; `flush()` runs it now (a reader that needs it done); with no window
drawing (a script, an offscreen check) it runs as soon as the event loop turns. Never later than LATEST_MS.

Several jobs asked by one click take turns, one per frame, in the order asked (a track picked: its settings panel,
then its piano roll, then the sound's compile): run together they made one long frame (~19 ms) after the click.
"""
from __future__ import annotations

import shiboken6
from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QGuiApplication

LATEST_MS = 50          # a window that should draw but doesn't still gets the work this soon
HEARD: list = []        # functions told when a run starts (the timing steps: what the click cost before it)


class AfterFrame(QObject):
    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn, self.due = fn, False

    def ask(self):
        if self.due:
            return
        self.due = True
        _TURNS.append(self)
        _TURNS.arm()

    def flush(self):
        if self.due:
            self.due = False
            _TURNS.drop(self)
            for f in HEARD:
                f()
            self._fn()


class _Turns(QObject):
    """The jobs waiting for a frame, oldest first: each frame on screen runs the first one."""

    def __init__(self):
        super().__init__()
        self._jobs: list[AfterFrame] = []
        self._armed, self._gen = False, 0

    def append(self, job):
        self._jobs.append(job)

    def drop(self, job):
        if job in self._jobs:
            self._jobs.remove(job)

    def arm(self):
        """Wait for the next frame (once, however many jobs wait). Each wait has its number: a frame or a timer from
        an older wait is ignored, so a job never runs before a frame of its own."""
        if self._armed or not self._jobs:
            return
        self._armed, self._gen = True, self._gen + 1
        gen = self._gen
        from PySide6.QtQuick import QQuickWindow
        wins = [w for w in QGuiApplication.topLevelWindows() if isinstance(w, QQuickWindow) and w.isExposed()]
        # (a window not on screen draws no frame: the work comes at the loop's next turn)
        for w in wins:
            w.frameSwapped.connect(lambda g=gen: QTimer.singleShot(0, self, lambda: self._run(g)),   # (the render
                                   Qt.ConnectionType.SingleShotConnection)     # thread may send it: queued to ours)
        QTimer.singleShot(LATEST_MS if wins else 0, self, lambda: self._run(gen))

    def _run(self, gen):
        if not self._armed or gen != self._gen:     # the frame and the timer both came, or an older wait
            return
        self._armed = False
        while self._jobs and not (self._jobs[0].due and shiboken6.isValid(self._jobs[0])):
            self._jobs.pop(0)                       # done, or its owner freed (a closed song's job never runs)
        try:
            if self._jobs:
                self._jobs[0].flush()               # (it leaves the list)
        finally:
            self.arm()                              # the next one, after the next frame


_TURNS = _Turns()
