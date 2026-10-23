"""The Export sheet's GIF size, measured off the GUI thread (rostrum2d/io/gif_size.py: a few frames drawn by their own
engine and GIF-encoded the export's way; 1–4 s). `bytes_for(key, prepare)` answers at once: the bytes for `key` when they
are known, None while they are being worked out (the sheet says "working it out"), or the failure in words. The
newest asked key wins: one at a time, a key asked during a run waits for it, older waiting ones are dropped. The answer
lands on the GUI thread and calls `on_landed` (the sheet re-reads its rows)."""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QCoreApplication, QObject, Signal


class GifGuess(QObject):
    _landed = Signal(object, object)          # (key, bytes or the failure in words): from the worker thread

    def __init__(self, on_landed, parent=None):
        super().__init__(parent)
        self._known: dict = {}                # key -> bytes (int) or the failure (str)
        self._running = None                  # the key being worked out
        self._waiting = None                  # (key, prepare) asked during a run
        self._on_landed = on_landed
        self._landed.connect(self._land)

    def bytes_for(self, key, prepare):
        """`prepare()` (on the GUI thread: it reads the document) -> `job`; `job()` -> bytes, on a worker thread."""
        if key in self._known:
            return self._known[key]
        if self._running is None:
            self._start(key, prepare)
        elif self._running != key:
            self._waiting = (key, prepare)
        return self._known.get(key)            # None while it runs (a document it can't read fails at once)

    def wait(self, timeout_s: float) -> bool:
        """Until the size being worked out has landed (scripted steps); False when it hasn't in time."""
        end = time.monotonic() + timeout_s
        while self._running is not None and time.monotonic() < end:
            QCoreApplication.processEvents()
            time.sleep(0.02)
        return self._running is None

    def _start(self, key, prepare):
        self._running = key
        try:
            job = prepare()
        except Exception as e:  # noqa: BLE001
            self._known[key], self._running = _failed(e), None
            return

        def run():
            try:
                found = int(job())
            except Exception as e:  # noqa: BLE001
                found = _failed(e)
            self._landed.emit(key, found)
        threading.Thread(target=run, name="gif-size", daemon=True).start()

    def _land(self, key, found):
        self._known[key] = found
        self._running = None
        if self._waiting is not None:
            k, prepare = self._waiting
            self._waiting = None
            if k not in self._known:
                self._start(k, prepare)
        self._on_landed()


def _failed(e: Exception) -> str:
    """Said on the sheet in place of the size, never a silent guess."""
    return f"couldn't work out the size: {getattr(e, 'plain', None) or e}"
