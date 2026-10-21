"""The background picture worker both canvases use (2D frames, 3D viewport): one thread owns one long-lived engine
process, jobs run off the GUI thread, and the newest picture is served to QML as image://<provider>/<serial>.

Newest request wins: `post_latest` replaces a job still waiting (stale pictures are never queued). `post_ordered`
jobs (picks) keep their order and run before the next picture. A failure is reported (`failed`, and on stderr),
never shown as if it worked; the next job tries again. `close` ends the engine.

An app subclasses `PictureWorker` and gives only its differences: `open_engine` (the engine to start), `handle`
(do one job on the engine) and `describe` (the words for a failed job).
"""
from __future__ import annotations

import sys
import threading
from collections import deque

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider


class ImageProvider(QQuickImageProvider):
    """Holds the newest picture; QML asks for it by id (the id only busts the cache)."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._lock, self._image = threading.Lock(), QImage()

    def put(self, image: QImage):
        with self._lock:
            self._image = image

    def requestImage(self, id_, size, requested):  # noqa: N802 (Qt's name)
        with self._lock:
            return self._image


def image_from_pixels(view, w: int, h: int, stride: int) -> QImage:
    """An RGBA picture from the engine's shared-memory slot; copied, because the slot is reused."""
    try:
        return QImage(view, w, h, stride, QImage.Format.Format_RGBA8888).copy()
    finally:
        view.release()


class PictureWorker(QObject):
    failed = Signal(str)

    def __init__(self, thread_name: str, parent=None):
        super().__init__(parent)
        self.provider = ImageProvider()
        self.serial = 0
        self._cv = threading.Condition()
        self._latest, self._ordered, self._busy, self._stop = None, deque(), False, False
        self._thread = threading.Thread(target=self._run, name=thread_name, daemon=True)

    def start(self):
        self._thread.start()

    # -- what an app gives -------------------------------------------------------------------------------
    def open_engine(self):
        raise NotImplementedError

    def handle(self, eng, job) -> None:
        raise NotImplementedError

    def describe(self, job, error: Exception) -> str:
        return f"Error: {job}: {error}"

    # -- asking ------------------------------------------------------------------------------------------
    def post_latest(self, job):
        with self._cv:
            self._latest = job
            self._cv.notify()

    def post_ordered(self, job):
        with self._cv:
            self._ordered.append(job)
            self._cv.notify()

    def idle(self) -> bool:
        with self._cv:
            return self._latest is None and not self._ordered and not self._busy

    def publish(self, image: QImage) -> int:
        """Serve `image` as the newest picture; returns its serial."""
        self.provider.put(image)
        self.serial += 1
        return self.serial

    # -- the thread --------------------------------------------------------------------------------------
    def _next(self):
        with self._cv:
            while self._latest is None and not self._ordered and not self._stop:
                self._cv.wait()
            if self._stop:
                return None
            if self._ordered:
                job = self._ordered.popleft()
            else:
                job, self._latest = self._latest, None
            self._busy = True
            return job

    def _run(self):
        eng = None
        try:
            while (job := self._next()) is not None:
                try:
                    eng = eng or self.open_engine()
                    self.handle(eng, job)
                except Exception as e:  # noqa: BLE001  any failure is reported, loudly
                    line = self.describe(job, e)
                    print(line, file=sys.stderr)
                    self.failed.emit(line)
                finally:
                    with self._cv:
                        self._busy = False
        finally:
            if eng is not None:
                eng.close()

    def close(self):
        with self._cv:
            self._stop = True
            self._cv.notify()
        self._thread.join(timeout=15)
