"""The playing clock's tick: a thread that sleeps the tick out and tells the screen thread (a queued signal).

A Qt timer on Windows fires in the system's timer steps, ~15.6 ms, whatever its interval or type; a window behind other
windows can't ask for finer ones (Windows 11 ignores timeBeginPeriod for it). A 4 ms clock then ticked every ~15 ms,
which beats against a 60 fps frame (16.7 ms): about one frame in ten was asked for a tick late and stayed up two
frames (critic r10, should-fix 13). Python's sleep uses a high-resolution wait on Windows, so this ticks on time. A tick
is sent only when the one before was handled: a busy screen thread never gets a queue of them.
"""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, Signal


class FrameClock(QObject):
    timeout = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop, self._ms = None, 4
        self._owed = threading.Event()                  # a tick sent and not yet handled
        self.timeout.connect(self._handled)             # runs on the screen thread (queued), after the tick's own handler

    def _handled(self):
        self._owed.clear()

    def isActive(self) -> bool:  # noqa: N802  (QTimer's name: playback.py uses it as one)
        return self._stop is not None

    def start(self, ms: int) -> None:
        self.stop()
        self._ms, self._stop = ms, threading.Event()
        self._owed.clear()
        threading.Thread(target=self._loop, args=(self._stop,), name="frame-clock", daemon=True).start()

    def stop(self) -> None:
        if self._stop is not None:
            self._stop.set()
            self._stop = None

    def _loop(self, stop: threading.Event):
        while True:
            time.sleep(self._ms / 1000)                 # high resolution on Windows (an Event's wait is not)
            if stop.is_set():
                return
            if not self._owed.is_set():
                self._owed.set()
                self.timeout.emit()
