"""The background picture worker both canvases use (2D frames, 3D viewport): one thread owns one long-lived engine
process, jobs run off the GUI thread, and the newest picture is served to QML as image://<provider>/<serial>.

Newest request wins: `post_latest` replaces a job still waiting (stale pictures are never queued). `post_ordered`
jobs (picks) keep their order and run before the next picture. Inside `asking()` a picture asked waits until the
block ends, so a question the same action asks right after its change (where the new layer sits) goes to the engine
first instead of queueing behind that picture. A failure is reported (`failed`, and on stderr),
never shown as if it worked; the next job tries again. `close` ends the engine. `behind` says a picture asked is not
served yet (the canvas's CatchUp mark), so an older picture is never presented as now.

An app subclasses `PictureWorker` and gives only its differences: `open_engine` (the engine to start), `handle`
(do one job on the engine) and `describe` (the words for a failed job).
"""
from __future__ import annotations

import sys
import threading
from collections import deque
from contextlib import contextmanager

from PySide6.QtCore import Property, QObject, Signal
from PySide6.QtGui import QImage

from .screen_images import ScreenImages


class ImageProvider(ScreenImages):
    """Holds the newest picture; QML asks for it by id (the id only busts the cache)."""

    def __init__(self):
        super().__init__()
        self._lock, self._image = threading.Lock(), QImage()

    def put(self, image: QImage):
        with self._lock:
            self._image = image

    def picture(self, id_):
        with self._lock:
            return self._image


FORMATS = {"rgba8": QImage.Format.Format_RGBA8888, "bgra8-premul": QImage.Format.Format_ARGB32_Premultiplied}


class ImagePool:
    """Pictures from an engine's shared-memory slot (copied, because the slot is reused), into a few pictures kept per
    size and reused in turn, so a frame costs one copy and no new memory. A picture still held elsewhere (the canvas
    showing it, a cache) is never written over: the pool's own copy is made anew then (QImage's copy on write).
    `bgra8-premul` is the screen's own form (Qt's ARGB32_Premultiplied): shown without a step on the screen thread.
    `keep`: how many in turn: more than the pictures kept elsewhere at once (a cache of recent pictures), made as needed."""

    def __init__(self, keep: int = 3):
        self._keep, self._kept, self._next = keep, [], 0

    def take(self, view, w: int, h: int, stride: int, fmt: str = "rgba8") -> QImage:
        try:
            form = FORMATS[fmt]
            first = self._kept[0] if self._kept else None
            if first is None or first.size().toTuple() != (w, h) or first.format() != form or first.bytesPerLine() != stride:
                self._kept, self._next = [], 0
            if self._next == len(self._kept):
                self._kept.append(QImage(w, h, form))
            img = self._kept[self._next]
            self._next = (self._next + 1) % self._keep
            img.bits()[:] = view                      # bits() first copies a picture still shared elsewhere
            return QImage(img)                        # shared: whoever keeps it keeps these pixels
        finally:
            view.release()


def image_from_pixels(view, w: int, h: int, stride: int, fmt: str = "rgba8") -> QImage:
    """A picture from an engine's shared-memory slot; copied, because the slot is reused (`ImagePool` for a stream)."""
    try:
        return QImage(view, w, h, stride, FORMATS[fmt]).copy()
    finally:
        view.release()


class PictureWorker(QObject):
    failed = Signal(str)
    behindChanged = Signal()       # `behind` changed (sent from the worker's thread too: Qt carries it to the screen's)

    def __init__(self, thread_name: str, parent=None):
        super().__init__(parent)
        self.provider = ImageProvider()
        self.serial = 0
        self._cv = threading.Condition()
        self._latest, self._ordered, self._busy, self._stop = None, deque(), False, False
        self._asking = 0                         # inside asking(): pictures wait, questions go
        self._behind = False                     # a picture asked is not on screen yet (CatchUp.qml marks it after 0.2 s)
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
        self._set_behind(True)                   # before the job is there: the worker can only say caught up after it
        with self._cv:
            self._latest = job
            self._cv.notify()

    @Property(bool, notify=behindChanged)
    def behind(self):
        """The picture shown is older than the one asked (INTERACTION.md 1.21 rule 7: the screen never lies): the
        canvas puts a soft "Updating" mark on it after 0.2 s (CatchUp.qml), never presenting it as now."""
        return self._behind

    def _set_behind(self, on: bool):
        if on != self._behind:
            self._behind = on
            self.behindChanged.emit()

    def post_ordered(self, job):
        with self._cv:
            self._ordered.append(job)
            self._cv.notify()

    @contextmanager
    def asking(self):
        """Questions first: a picture asked inside waits until the block ends (the newest one is then drawn); the
        ordered jobs (place, ask) asked inside reach the engine at once. For an action that changes the document and
        then asks about the change: the change's picture would otherwise hold the engine while the question waits."""
        with self._cv:
            self._asking += 1
        try:
            yield
        finally:
            with self._cv:
                self._asking -= 1
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
            while not self._ordered and (self._latest is None or self._asking) and not self._stop:
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
                        caught_up = self._latest is None
                    if caught_up:
                        self._set_behind(False)
        finally:
            if eng is not None:
                eng.close()

    def close(self):
        with self._cv:
            self._stop = True
            self._cv.notify()
        self._thread.join(timeout=15)
