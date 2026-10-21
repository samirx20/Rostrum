"""The project's shared markers on a screen (rostrum_core.markers): a list QML can draw as flags, kept fresh when
another app or an agent changes them, and the one snap rule for anything dragged along time."""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from rostrum_core.markers import times

POLL_MS = 500          # another process (an agent, Sound) may move a marker: look at the file this often (cheap)


class MarkerWatch(QObject):
    changed = Signal()

    def __init__(self, folder, parent=None):
        super().__init__(parent)
        self.folder, self.times = folder, times(folder)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        if folder is not None:
            self._timer.start(POLL_MS)

    def refresh(self):
        now = times(self.folder)
        if now != self.times:
            self.times = now
            self.changed.emit()

    def rows(self) -> list[dict]:
        """[{name, at}] by time, for the ruler's flags."""
        return [{"name": n, "at": t} for n, t in self.times.items()]

    def snap(self, t: float, within: float) -> float:
        """t moved onto the nearest marker when one is within `within` seconds; else t unchanged."""
        near = min(self.times.values(), key=lambda m: abs(m - t), default=None)
        return near if near is not None and abs(near - t) <= within else t

    def close(self):
        self._timer.stop()
