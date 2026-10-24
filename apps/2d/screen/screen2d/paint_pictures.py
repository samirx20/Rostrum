"""Paint pictures made off the screen's thread. A change to a drawing (a stroke lands, an erase, an undo) needs that
drawing's picture made again: its strokes stamped, its layers put together, a PNG written (canvas.png, the very file
export reads). On the screen's thread that froze the window for most of a second per stroke. So the scene is described
with stand-ins for pictures not made yet (scene.describe `later`), this makes them on its own thread, and `done` says
so: the bridge then describes again (every picture made now) and draws. Newest wins: a batch still waiting when a newer
one comes is dropped (the newer change has its own pictures). A picture that fails says why (`failed`), loudly.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal
from rostrum_paint import canvas


class PaintPictures(QObject):
    done = Signal(object)        # the token the batch was asked with (the document state it was described from)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wake, self._next, self._closed = threading.Condition(), None, False
        self._thread = threading.Thread(target=self._run, name="paint-pictures", daemon=True)
        self._thread.start()

    def make(self, jobs: list, token) -> None:
        """Make each (canvas, w, h) picture, then `done(token)`."""
        with self._wake:
            self._next = (list(jobs), token)
            self._wake.notify()

    def _run(self):
        while True:
            with self._wake:
                while self._next is None and not self._closed:
                    self._wake.wait()
                if self._closed:
                    return
                (jobs, token), self._next = self._next, None
            try:
                for frame, w, h in jobs:
                    canvas.png(frame, w, h)
            except Exception as e:  # noqa: BLE001  said on screen, the frame isn't drawn
                self.failed.emit(f"Error: the drawing's picture could not be made: {e}")
                continue
            self.done.emit(token)

    def close(self):
        with self._wake:
            self._closed = True
            self._wake.notify()
        self._thread.join(timeout=10)
