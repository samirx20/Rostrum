"""When Qt builds the items it makes ahead (a list's rows past the view: ListView `cacheBuffer`, asynchronous Loaders):
in idle time, in short slices, and never while a mouse button is held.

Qt's own controller builds them in the time left after each drawn frame. A drag draws a frame per move, so every move
paid for row-making on top of its own work: at 200 layers, after the list jumped to a far row, a one-dot drag was
~20-30 ms a move, against ~6-10 once the rows were made (2D critic r10, must-fix 2). Here the building waits while a
button is down (a drag, a held slider) and otherwise runs a few ms at a time between events, so input and frames
always come first. Items in view are never waiting on this: a list makes those at once.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlIncubationController

SLICE_MS = 4        # building per turn of the event loop: input and frames wait at most this long
HELD_MS = 50        # while a button is down, look again this often


class IdleIncubation(QQmlIncubationController):
    def __init__(self, parent: QObject):
        super().__init__()
        self._timer = QTimer(parent)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._turn)

    def incubatingObjectCountChanged(self, count: int):  # noqa: N802  (Qt's name)
        if count and not self._timer.isActive():
            self._timer.start(0)

    def _turn(self):
        if not self.incubatingObjectCount():
            return
        if QGuiApplication.mouseButtons() != Qt.MouseButton.NoButton:
            self._timer.start(HELD_MS)
            return
        self.incubateFor(SLICE_MS)
        if self.incubatingObjectCount():
            self._timer.start(0)


def install(engine) -> None:
    """Give `engine` the idle controller (before its first window is made: a window gives its own to an engine that has none)."""
    engine._incubation = IdleIncubation(engine)      # held by the engine: Qt keeps only a pointer
    engine.setIncubationController(engine._incubation)
