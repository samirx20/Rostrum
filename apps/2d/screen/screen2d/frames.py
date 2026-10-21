"""The canvas picture: frames rendered by the 2D engine (the same path as export: preview ≡ export), off the GUI
thread, newest request wins. The newest picture is served to QML as image://frame/<n>. The worker itself is the
kit's (rostrum_gui.frames.PictureWorker); this file is what is 2D's: the engine, the scene sent only when it
changed, and how a frame is read.

On Windows the frame comes through the engine's shared memory (`pixels`, no PNG); elsewhere, until the engine has
it there, through a PNG.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QImage
from rostrum_gui.frames import ImageProvider, PictureWorker, image_from_pixels

SCRATCH = Path.home() / ".rostrum" / "cache" / "screen2d" / str(os.getpid())
FrameProvider = ImageProvider


def open_engine():
    """The renderer the canvas uses (swap here, nowhere else)."""
    from rostrum2d.engine import Engine
    return Engine()


def _frame(eng, t: float, png: Path) -> QImage:
    if sys.platform == "win32":
        return image_from_pixels(*eng.pixels(t))
    eng.still(t, png)
    return QImage(str(png))


class FrameRenderer(PictureWorker):
    ready = Signal(int)          # serial of the newest frame

    def __init__(self, parent=None):
        super().__init__("frames2d", parent)
        self._loaded = None
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.start()

    def request(self, scene: dict, t: float):
        self.post_latest((scene, t))

    def open_engine(self):
        return open_engine()

    def handle(self, eng, job):
        scene, t = job
        if scene != self._loaded:
            eng.load(scene)
            self._loaded = scene
        image = _frame(eng, t, SCRATCH / "frame.png")
        if image.isNull():
            raise RuntimeError(f"the engine's frame could not be read: {SCRATCH / 'frame.png'}")
        self.ready.emit(self.publish(image))

    def describe(self, job, error):
        return f"Error: canvas frame at {job[1]:.2f} s: {error}"

    def close(self):
        super().close()
        shutil.rmtree(SCRATCH, ignore_errors=True)
