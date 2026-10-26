"""The canvas picture: frames rendered by the 2D engine (the same path as export: preview ≡ export), off the GUI
thread, newest request wins. The newest picture is served to QML as image://frame/<n>. The worker itself is the
kit's (rostrum_gui.frames.PictureWorker); this file is what is 2D's: the engine, the scene sent only when it
changed, and how a frame is read.

On Windows the frame comes through the engine's shared memory (`pixels`, no PNG) in the screen's own form, copied
into pictures reused in turn (the kit's ImagePool); elsewhere, until the engine has it there, through a PNG. While
playing each frame asks for the next one ahead (playback.py `ahead`): the engine draws it while this one is shown.

Paused, a job asks for the world picture (`world`: the world rectangle the view shows, at the size shown, the
frame's quad holding the export; world_view.py), served as image://frame/<n> with its rectangle (`pictured`); the
pictures drawn last are kept (`WorldCache`), so a view or time seen a moment ago shows again without the engine.
Playing, a job asks for the export at the playing size. A job may ask for layers' places (`place`: the paint target's
edge while painting, painter.py; in world px with a world picture), sent with the frame; `place()` asks for one now
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
from rostrum_gui.frames import ImagePool, ImageProvider, PictureWorker, image_from_pixels
from rostrum2d import settings
from rostrum_core import scratch

from .playstats import STATS

SCRATCH = settings.cache_dir("screen2d") / str(os.getpid())
FrameProvider = ImageProvider


def open_engine():
    """The renderer the canvas uses (swap here, nowhere else)."""
    from rostrum2d.engine import Engine
    return Engine()


def _frame(eng, t: float, png: Path, samples: int | None, scale: float, place=None, view=None, world=None,
           pool: ImagePool | None = None, ahead: float | None = None) -> QImage:
    """The frame as a picture. With `pool` (the canvas) in the screen's own form, into the pool's reused pictures;
    without, straight RGBA8, a picture of its own."""
    if sys.platform == "win32":
        with STATS.stage("pixels"):
            got = eng.pixels(t, samples, scale, view, place, world, screen=pool is not None, ahead=ahead)
        STATS.engine(eng.timing)
        with STATS.stage("image"):
            return pool.take(*got, eng.format) if pool is not None else image_from_pixels(*got)
    if view or world:                                      # a crop or the world needs the engine's pixels (Windows for now)
        raise RuntimeError("the world view needs the engine's shared pixels (Windows for now)")
    eng.still(t, png)                                      # full size until the engine's pixels come to the Mac
    eng.placed = eng.place(t, place) if place else {}
    return QImage(str(png))


_TOLD = set()                    # what was said in the status line already: once per app run


class WorldCache:
    """The world pictures drawn last, by what they were drawn from (the scene described, t, motion-blur steps, the
    rectangle and its scale): a view or time seen a moment ago shows again without the engine. The scene is a new
    object on every change, so a changed piece never meets an old picture."""
    MOST = 12                    # about 6 MB each at Sam's screen

    def __init__(self):
        self._scene, self._kept = None, []      # the scene the pictures were drawn from (held: its id stays its own)

    @staticmethod
    def key(scene, t, samples, world, place):
        return None if place or world is None else (t, samples, tuple(sorted(world.items())))

    def get(self, scene, key):
        if scene is not self._scene:            # pictures of an older scene never show again: let them go now
            self._scene, self._kept = scene, []
        if not key:
            return None
        return next((img for k, img in self._kept if k == key), None)

    def put(self, scene, key, image):
        if key:
            if scene is not self._scene:
                self._scene, self._kept = scene, []
            self._kept = self._kept[-(self.MOST - 1):] + [(key, image)]


class FrameRenderer(PictureWorker):
    ready = Signal(int, object)  # serial of the newest frame, and the tag it was asked with (what it was rendered from)
    note = Signal(str)           # a plain notice for the status line (painting on the processor: no graphics driver)
    placed = Signal(object)      # {id: place} the job asked for, just before its `ready`
    pictured = Signal(int, object)  # the newest frame's serial and its world rect {x, y, w, h, scale} (None: the export), before `ready`

    def __init__(self, parent=None):
        super().__init__("frames2d", parent)
        self._kept = WorldCache()
        self._pool = ImagePool(WorldCache.MOST + 3)
        self._loaded = None
        SCRATCH.mkdir(parents=True, exist_ok=True)
        scratch.sweep_later(SCRATCH.parent)      # folders killed runs left (a day old, no process owns): once, well after the start
        self.start()

    def request(self, scene: dict, t: float, samples: int | None = None, scale: float = 1.0, tag=None, world=None, place=None,
                ahead: float | None = None):
        """Draw `scene` at `t`. `samples`: motion-blur steps instead of the composition's; `scale`: its size × a step of
        shown.VIEW_SCALES (the export while playing). The same scene and engine either way (preview ≡ export). `tag` comes back
        with the frame (`ready`): the state it was rendered from (shown.py). `world` {x, y, w, h, scale}: the world
        picture of that rectangle instead (`pictured` says which); `place`: layer ids whose places come with the frame
        (`placed`, world px with a world picture). `ahead`: the time asked for next (playing): the engine draws it while
        this one is shown (ENGINE_CONTRACT.md › ahead)."""
        self.post_latest((scene, t, samples, scale, tag, world, place, ahead))

    def request_edit(self, scene: dict, edits: list[dict], t: float, samples: int | None = None, scale: float = 1.0, tag=None,
                     world=None, place=None, ahead=None):
        """Draw `scene` with `edits` (engine `edit`: absolute values, so a newer request may replace an older one) at `t`:
        a drag of many layers (ghost_move.py). Never kept in the frame cache; the next `request` loads its scene whole."""
        self.post_latest(("edit", scene, edits, t, samples, scale, tag, world, place, ahead))

    def place(self, scene: dict, t: float, ids: list[str], timeout_s: float = 10.0, world: bool = False) -> dict:
        """The layers' places at `t` now (ahead of the next picture), from the engine that draws the canvas. Raises
        what the engine said, or on no answer within `timeout_s`. `world`: places in world px (what the canvas shows)
        instead of the export's."""
        box = {"done": threading.Event()}
        self.post_ordered(("place", scene, t, ids, box, world))
        if not box["done"].wait(timeout_s):
            raise RuntimeError(f"the drawing engine gave no place for {', '.join(ids)} within {timeout_s:.0f} s")
        if "error" in box:
            raise box["error"]
        return box["places"]

    def ask(self, scene: dict, fn, done) -> None:
        """Ask the canvas's engine something with `scene` loaded (`fn(eng)`, e.g. the posed bones: rig_view.py), off the
        GUI thread; `done(answer, error)` is called on the worker thread (emit a signal from it)."""
        self.post_ordered(("ask", scene, fn, done))

    def still(self, scene: dict, t: float, samples: int | None, done, world: dict | None = None) -> None:
        """The whole frame of `scene` at `t` at full size, as straight RGBA8 (h × w × 4 numpy), drawn off the GUI
        thread by the canvas's engine; `world` {x, y, w, h, scale}: that world picture instead (the eraser's view under
        its layer: wet.py); `done(pixels, error)` on the worker."""
        import numpy as np

        def grab(eng):
            image = _frame(eng, t, SCRATCH / "still.png", samples, 1.0, world=world).convertToFormat(QImage.Format.Format_RGBA8888)
            if image.isNull():
                raise RuntimeError(f"the engine's frame could not be read at {t:.2f} s")
            rows = np.frombuffer(image.constBits(), np.uint8).reshape(image.height(), image.bytesPerLine())
            return rows[:, :image.width() * 4].reshape(image.height(), image.width(), 4).copy()
        self.ask(scene, grab, done)

    def open_engine(self):
        return open_engine()

    def _load(self, eng, scene, edits=False):
        if scene is not self._loaded or (getattr(eng, "edited", False) and not edits):     # (a drag's edits: on the scene held; anything
            # else after them loads its scene whole, engine.load). The bridge describes a new scene only on a change
            with STATS.stage("load"):
                eng.load(scene)
            self._loaded = scene
            if eng.fallback and eng.fallback not in _TOLD:
                _TOLD.add(eng.fallback)
                self.note.emit(eng.fallback)

    def handle(self, eng, job):
        if job[0] == "place":
            _, scene, t, ids, box, world = job
            try:
                self._load(eng, scene)
                box["places"] = eng.place(t, ids, world=world)
            except Exception as e:  # noqa: BLE001  handed to the asker, who raises it
                box["error"] = e
            box["done"].set()
            return
        if job[0] == "edit":
            _, scene, edits, t, samples, scale, tag, world, place, ahead = job
            self._load(eng, scene, edits=True)
            eng.edit(edits)
            image = _frame(eng, t, SCRATCH / "frame.png", samples, scale, place, None, world, self._pool, ahead)
            self.placed.emit(eng.placed if place else {})
            serial = self.publish(image)
            self.pictured.emit(serial, world)
            self.ready.emit(serial, tag)
            return
        if job[0] == "ask":
            _, scene, fn, done = job
            try:
                self._load(eng, scene)
                answer = fn(eng)
            except Exception as e:  # noqa: BLE001  handed to the asker, who says it
                return done(None, e)
            return done(answer, None)
        scene, t, samples, scale, tag, world, place, ahead = job
        key = WorldCache.key(scene, t, samples, world, place)
        image = self._kept.get(scene, key)
        if image is None:
            self._load(eng, scene)
            image = _frame(eng, t, SCRATCH / "frame.png", samples, scale, place, None, world, self._pool, ahead)
            if image.isNull():
                raise RuntimeError(f"the engine's frame could not be read: {SCRATCH / 'frame.png'}")
            self._kept.put(scene, key, image)
            self.placed.emit(eng.placed if place else {})
        serial = self.publish(image)
        self.pictured.emit(serial, world)
        self.ready.emit(serial, tag)
        if eng.notice:                                      # it died and was restarted (engine.py): said once
            self.note.emit(eng.notice)
            eng.notice = None

    def describe(self, job, error):
        if getattr(error, "plain", False):                  # a whole sentence for the person (engine.GAVE_UP)
            return f"Error: {error}"
        what, t = ("place", job[2]) if job[0] == "place" else ("frame", job[3]) if job[0] == "edit" else ("frame", job[1])
        return f"Error: canvas {what} at {t:.2f} s: {error}"

    def close(self):
        super().close()
        shutil.rmtree(SCRATCH, ignore_errors=True)
