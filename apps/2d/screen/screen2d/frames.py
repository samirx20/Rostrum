"""The canvas picture: frames rendered by the 2D engine (the same path as export: preview ≡ export), off the GUI
thread, newest request wins. The newest picture is served to QML as image://frame/<n>. The worker itself is the
kit's (rostrum_gui.frames.PictureWorker); this file is what is 2D's: the engine, the scene sent only when it
changed, and how a frame is read.

On Windows the frame comes through the engine's shared memory (`pixels`, no PNG); elsewhere, until the engine has
it there, through a PNG.

Zoomed in past Full, a job also draws the visible part again at the size shown (`crop`: the engine's `view`, the same
paint as any frame), served as image://framecrop/<n> over the frame (sharp.py). A job may ask for layers' places
(`place`: the paint target's edge while painting, painter.py), sent with the frame; `place()` asks for one now
(the pen's press: painting's one mapping, rostrum2d/placement.py).
"""
from __future__ import annotations

import os
import shutil
import sys
import threading
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


def _frame(eng, t: float, png: Path, samples: int | None, scale: float, place=None, view=None) -> QImage:
    if sys.platform == "win32":
        with STATS.stage("pixels"):
            got = eng.pixels(t, samples, scale, view, place)
        with STATS.stage("image"):
            return image_from_pixels(*got)
    if view:                                               # a crop needs the engine's pixels (Windows for now)
        return QImage()
    eng.still(t, png)                                      # full size until the engine's pixels come to the Mac
    eng.placed = eng.place(t, place) if place else {}
    return QImage(str(png))


_TOLD = set()                    # what was said in the status line already: once per app run


class FrameRenderer(PictureWorker):
    ready = Signal(int, object)  # serial of the newest frame, and the tag it was asked with (what it was rendered from)
    note = Signal(str)           # a plain notice for the status line (painting on the processor: no graphics driver)
    placed = Signal(object)      # {id: place} the job asked for, just before its `ready`
    cropped = Signal(int, object)  # serial of the newest sharp crop (0: none) and its comp px rect {x, y, w, h}

    def __init__(self, parent=None):
        super().__init__("frames2d", parent)
        self.crops = ImageProvider()                        # image://framecrop/<n>
        self._crop_serial = 0
        self._loaded = None
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.start()

    def request(self, scene: dict, t: float, samples: int | None = None, scale: float = 1.0, tag=None, crop=None, place=None):
        """Draw `scene` at `t`. `samples`: motion-blur steps instead of the composition's; `scale`: 1, 0.5 or 0.25 of
        its size (fast playback, dragging). The same scene and engine either way, so a paused frame and the export are
        the full picture. `tag` comes back with the frame (`ready`): the state it was rendered from (shown.py).
        `crop` {x, y, w, h, scale}: the visible part drawn again at the size shown (`cropped`); `place`: layer ids
        whose places come with the frame (`placed`)."""
        self.post_latest((scene, t, samples, scale, tag, crop, place))

    def place(self, scene: dict, t: float, ids: list[str], timeout_s: float = 10.0) -> dict:
        """The layers' places at `t` now (ahead of the next picture), from the engine that draws the canvas. Raises
        what the engine said, or on no answer within `timeout_s`."""
        box = {"done": threading.Event()}
        self.post_ordered(("place", scene, t, ids, box))
        if not box["done"].wait(timeout_s):
            raise RuntimeError(f"the drawing engine gave no place for {', '.join(ids)} within {timeout_s:.0f} s")
        if "error" in box:
            raise box["error"]
        return box["places"]

    def open_engine(self):
        return open_engine()

    def _load(self, eng, scene):
        if scene is not self._loaded:                       # the bridge describes a new scene only on a change
            with STATS.stage("load"):
                eng.load(scene)
            self._loaded = scene
            if eng.fallback and eng.fallback not in _TOLD:
                _TOLD.add(eng.fallback)
                self.note.emit(eng.fallback)

    def handle(self, eng, job):
        if job[0] == "place":
            _, scene, t, ids, box = job
            try:
                self._load(eng, scene)
                box["places"] = eng.place(t, ids)
            except Exception as e:  # noqa: BLE001  handed to the asker, who raises it
                box["error"] = e
            box["done"].set()
            return
        scene, t, samples, scale, tag, crop, place = job
        self._load(eng, scene)
        image = _frame(eng, t, SCRATCH / "frame.png", samples, scale, place)
        if image.isNull():
            raise RuntimeError(f"the engine's frame could not be read: {SCRATCH / 'frame.png'}")
        self.placed.emit(eng.placed if place else {})
        self.ready.emit(self.publish(image), tag)
        sharp = _frame(eng, t, SCRATCH / "crop.png", samples, 1.0, None, crop) if crop else QImage()
        if not sharp.isNull():
            self.crops.put(sharp)
            self._crop_serial += 1
        self.cropped.emit(self._crop_serial if not sharp.isNull() else 0, crop or {})
        if eng.notice:                                      # it died and was restarted (engine.py): said once
            self.note.emit(eng.notice)
            eng.notice = None

    def describe(self, job, error):
        if getattr(error, "plain", False):                  # a whole sentence for the person (engine.GAVE_UP)
            return f"Error: {error}"
        what, t = ("place", job[2]) if job[0] == "place" else ("frame", job[1])
        return f"Error: canvas {what} at {t:.2f} s: {error}"

    def close(self):
        super().close()
        shutil.rmtree(SCRATCH, ignore_errors=True)
