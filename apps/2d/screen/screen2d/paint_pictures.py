"""Paint pictures made off the screen's thread. A change to a drawing (a stroke lands, an erase, an undo) needs that
drawing's picture made again: its strokes stamped, its layers put together, a PNG written (canvas.png, the very file
export reads). On the screen's thread that froze the window for most of a second per stroke. So the scene is described
with stand-ins for pictures not made yet (scene.describe `later`), this makes them on its own thread, and `done` says
so: the bridge then describes again (every picture made now) and draws. Newest wins: a batch still waiting when a newer
one comes is dropped (the newer change has its own pictures). A picture that fails says why (`failed`), loudly.
"""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, Signal
from rostrum2d import drawing


ROUND = 0.1     # s of Drawn so far pictures made before the screen draws them (each round describes the scene again)


class PaintPictures(QObject):
    done = Signal(object)        # the token the batch was asked with (the document state it was described from)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wake, self._next, self._closed = threading.Condition(), None, False
        self._thread = threading.Thread(target=self._run, name="paint-pictures", daemon=True)
        self._thread.start()

    def make(self, jobs: list, token) -> None:
        """Run each job (a call making one picture: drawing.picture / drawing.inked's `later`), then `done(token)`."""
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
                ahead = all(getattr(job, "ahead", False) for job in jobs)
                start, each = time.perf_counter(), drawing.WORKERS if ahead else len(jobs)
                for i in range(0, len(jobs), max(1, each)):
                    drawing.make_all(jobs[i:i + each])
                    if ahead and (time.perf_counter() - start > ROUND or self._next is not None):
                        break               # pictures the screen draws without waiting for (write_on.Ahead): those
                        #                     made show each round, and the screen asks again for the rest (nearest first)
            except Exception as e:  # noqa: BLE001  said on screen, the frame isn't drawn
                self.failed.emit(f"Error: the drawing's picture could not be made: {e}")
                continue
            self.done.emit(token)

    def close(self):
        with self._wake:
            self._closed = True
            self._wake.notify()
        self._thread.join(timeout=10)
