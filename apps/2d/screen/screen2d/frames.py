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
from rostrum2d import settings

from .playstats import STATS

SCRATCH = settings.cache_dir("screen2d") / str(os.getpid())
FrameProvider = ImageProvider


def open_engine():
    """The renderer the canvas uses (swap here, nowhere else)."""
    from rostrum2d.engine import Engine
    return Engine()


def _frame(eng, t: float, png: Path, samples: int | None, scale: float) -> QImage:
    if sys.platform == "win32":
        with STATS.stage("pixels"):
            got = eng.pixels(t, samples, scale)
        with STATS.stage("image"):
            return image_from_pixels(*got)
    eng.still(t, png)                                      # full size until the engine's pixels come to the Mac
    return QImage(str(png))


_TOLD = set()                    # what was said in the status line already: once per app run


class FrameRenderer(PictureWorker):
    ready = Signal(int)          # serial of the newest frame
    note = Signal(str)           # a plain notice for the status line (painting on the processor: no graphics driver)

    def __init__(self, parent=None):
        super().__init__("frames2d", parent)
        self._loaded = None
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.start()

    def request(self, scene: dict, t: float, samples: int | None = None, scale: float = 1.0):
        """Draw `scene` at `t`. `samples`: motion-blur steps instead of the composition's; `scale`: 1, 0.5 or 0.25 of
        its size (both for fast playback). The same scene and engine either way, so a paused frame and the export are
        the full picture."""
        self.post_latest((scene, t, samples, scale))

    def open_engine(self):
        return open_engine()

    def handle(self, eng, job):
        scene, t, samples, scale = job
        if scene is not self._loaded:                       # the bridge describes a new scene only on a change
            with STATS.stage("load"):
                eng.load(scene)
            self._loaded = scene
            if eng.fallback and eng.fallback not in _TOLD:
                _TOLD.add(eng.fallback)
                self.note.emit(eng.fallback)
        image = _frame(eng, t, SCRATCH / "frame.png", samples, scale)
        if image.isNull():
            raise RuntimeError(f"the engine's frame could not be read: {SCRATCH / 'frame.png'}")
        self.ready.emit(self.publish(image))
        if eng.notice:                                      # it died and was restarted (engine.py): said once
            self.note.emit(eng.notice)
            eng.notice = None

    def describe(self, job, error):
        if getattr(error, "plain", False):                  # a whole sentence for the person (engine.GAVE_UP)
            return f"Error: {error}"
        return f"Error: canvas frame at {job[1]:.2f} s: {error}"

    def close(self):
        super().close()
        shutil.rmtree(SCRATCH, ignore_errors=True)
