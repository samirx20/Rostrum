"""Work that may show one frame after the pointer's own: `AfterFrame(fn).ask()` runs `fn` once, right after the next
frame of the app's window is on screen (its frameSwapped), so what the click itself changes (a row lit, an outline)
is drawn first and the rest (a pick's settings panel) lands in the frame after, instead of both waiting for each
other. A second ask before it ran is the same run; `flush()` runs it now (a reader that needs it done); with no window
drawing (a script, an offscreen check) it runs as soon as the event loop turns. Never later than LATEST_MS.
"""
from __future__ import annotations

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
        from PySide6.QtQuick import QQuickWindow
        wins = [w for w in QGuiApplication.topLevelWindows() if isinstance(w, QQuickWindow) and w.isExposed()]
        # (a window not on screen draws no frame: the work comes at the loop's next turn)
        for w in wins:
            w.frameSwapped.connect(self._swapped, Qt.ConnectionType.SingleShotConnection)
        QTimer.singleShot(LATEST_MS if wins else 0, self, self.flush)

    def _swapped(self):
        QTimer.singleShot(0, self, self.flush)      # after the swap's own work, on the next turn of the loop

    def flush(self):
        if self.due:
            self.due = False
            for f in HEARD:
                f()
            self._fn()
