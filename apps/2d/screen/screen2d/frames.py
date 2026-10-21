"""The canvas picture: frames rendered by the 2D engine (the same path as export: preview ≡ export), off the GUI
thread, newest request wins (a request made while one renders replaces any waiting one; stale frames are never
queued). The newest picture is served to QML as image://frame/<n>.

One worker thread owns one long-lived engine process (rostrum2d.engine.Engine); `close` ends it. The scene is
sent again only when it changed. On Windows the frame comes through the engine's shared memory (`pixels`, no PNG);
elsewhere, until the engine has it there, through a PNG.
A failed frame is reported (`failed`), never shown as if it worked; the next request tries again.
"""
from __future__ import annotations

import os
import shutil
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider

SCRATCH = Path.home() / ".rostrum" / "cache" / "screen2d" / str(os.getpid())


def open_engine():
    """The renderer the canvas uses (swap here, nowhere else)."""
    from rostrum2d.engine import Engine
    return Engine()


class FrameProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._lock, self._image = threading.Lock(), QImage()

    def put(self, image: QImage):
        with self._lock:
            self._image = image

    def requestImage(self, id_, size, requested):  # noqa: N802 (Qt's name)
        with self._lock:
            return self._image


def _frame(eng, t: float, png: Path) -> QImage:
    if sys.platform == "win32":
        view, w, h, stride = eng.pixels(t)
        image = QImage(view, w, h, stride, QImage.Format.Format_RGBA8888).copy()   # copied: the slot is reused
        view.release()
        return image
    eng.still(t, png)
    return QImage(str(png))


class FrameRenderer(QObject):
    ready = Signal(int)          # serial of the newest frame
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.provider = FrameProvider()
        self._cv = threading.Condition()
        self._pending, self._busy, self._stop, self._serial = None, False, False, 0
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._run, name="frames2d", daemon=True)
        self._thread.start()

    def request(self, scene: dict, t: float):
        with self._cv:
            self._pending = (scene, t)
            self._cv.notify()

    def idle(self) -> bool:
        with self._cv:
            return self._pending is None and not self._busy

    def _run(self):
        eng, loaded = None, None
        png = SCRATCH / "frame.png"
        try:
            while True:
                with self._cv:
                    while self._pending is None and not self._stop:
                        self._cv.wait()
                    if self._stop:
                        return
                    (scene, t), self._pending, self._busy = self._pending, None, True
                try:
                    eng = eng or open_engine()
                    if scene != loaded:
                        eng.load(scene)
                        loaded = scene
                    image = _frame(eng, t, png)
                    if image.isNull():
                        raise RuntimeError(f"the engine's frame could not be read: {png}")
                    self.provider.put(image)
                    self._serial += 1
                    self.ready.emit(self._serial)
                except Exception as e:  # noqa: BLE001  any failure is reported, loudly
                    print(f"Error: canvas frame at {t:.2f} s: {e}", file=sys.stderr)
                    self.failed.emit(f"Error: canvas frame at {t:.2f} s: {e}")
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
        shutil.rmtree(SCRATCH, ignore_errors=True)
