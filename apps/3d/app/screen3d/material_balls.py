"""Material balls (SPEC §6.1): a small rendered sphere per material setting, for the picker and the Materials list.

Each ball is a real Storm picture through the balls' own engine and thread (BallRenderer: never the viewport's, so a
ball can never upset the viewport's scene or its selection outline), lit by one fixed set-up (ball_studio.py: a key softbox up left, a soft fill, a rim behind, on a mid-grey
background). A ball is made once per set of field values and engine build, then kept in memory and on disk
(<cache>/3d/balls/<hash>.png, the oldest beyond CAP removed), and served to QML as image://ball/<hash>.

    balls = MaterialBalls(BallRenderer())            # None (no engine, tests): url() is "" and nothing fails
    balls.url(values) -> "image://ball/<hash>", or "" while it renders; `updated` fires when new balls land
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider
from rostrum_core.cache import default_root, put_file
from rostrum_gui.frames import PictureWorker, image_from_pixels

from screen3d.ball_studio import LOOK as STUDIO_LOOK, studio_picture
from rostrum3d import build, fields as F, run_source
from rostrum3d.compile import describe
from rostrum3d.runtime import find_exe

SIZE, SPACING, CAP = 96, 6.0, 600            # pixels; metres between balls in one scene; files kept on disk
SETUP_VERSION = 2                            # raise when the lighting or framing below changes: every ball redraws
STAGE = '''
light("studio", kind="dome", texture="{picture}", seenByCamera=False)
camera("cam", z=4)
shot("s", camera="cam", fps=24, start=0, end=1, background="#808080")
'''


def folder() -> Path:
    return default_root() / "3d" / "balls"


def engine_stamp() -> str:
    """The engine build's identity (a new build draws every ball again)."""
    exe = find_exe()
    st = exe.stat() if exe.exists() else None
    return f"{exe.name}:{st.st_size}:{int(st.st_mtime)}" if st else "missing"


def ball_values(values: dict) -> dict:
    """The material fields that apply (a whole material item may be given): ids, names and switched-off settings go,
    and a 2D render (a project's own file) is left out of the ball."""
    names = {p.name for p in F.FIELDS["material"]} - {"emissionRender"}
    kept = {k: v for k, v in values.items() if k in names}
    off = set(F.not_valid("material", {**F.defaults("material"), **kept}, kept))
    return {k: v for k, v in kept.items() if k not in off}


def ball_key(values: dict, stamp: str) -> str:
    recipe = {"v": SETUP_VERSION, "studio": STUDIO_LOOK, "engine": stamp, "size": SIZE, "values": values}
    return hashlib.sha256(json.dumps(recipe, sort_keys=True, default=str).encode()).hexdigest()[:24]


def scene_of(batch: dict[str, dict]) -> dict:
    """One scene holding a ball per material (in a row along x), for `render_balls`."""
    doc = run_source(STAGE.format(picture=studio_picture(folder()).replace("\\", "/")), "balls.py")
    for i, (key, values) in enumerate(batch.items()):
        doc["materials"].append(build.make("material", f"m{i}", {**values, "name": key}, "material ball"))
        doc["items"].append(build.make("mesh", f"ball{i}", {"shape": "sphere", "radius": 0.5, "segments": 48,
                                                             "material": f"m{i}", "x": i * SPACING}, "material ball"))
    return describe(doc, "s")


def render_balls(eng, batch: dict[str, dict], size: int = SIZE) -> dict[str, QImage]:
    """{key: field values} → {key: picture}: one scene, one free-camera Storm view per ball, on `eng`."""
    eng.ensure_scene(scene_of(batch))
    out = {}
    for i, key in enumerate(batch):
        x = i * SPACING
        *pixels, _ = eng.view(eye=[x, 0.0, 3.2], target=[x, 0.0, 0.0], fov=21, frame=0, width=size, height=size,
                              renderer="storm", studio=1.0, sceneLights=True, ao=0, dof=False, selected=[], view="")
        image = image_from_pixels(*pixels)
        if image.isNull():
            raise RuntimeError("a material ball's picture could not be read from the engine's shared memory")
        out[key] = image
    return out


class BallRenderer(PictureWorker):
    """A thread and an engine process of the balls' own. The engine is ended after each batch (its graphics memory goes
    back); the next batch starts a fresh one."""

    def __init__(self, parent=None):
        super().__init__("balls3d", parent)
        self.start()

    def open_engine(self):
        from rostrum3d.engine import Engine
        return Engine()

    def call(self, fn):
        """Run `fn(engine)` here, in order, never dropped."""
        self.post_ordered(fn)

    def handle(self, eng, job):
        try:
            job(eng)
        finally:
            eng.release()

    def describe(self, job, error):
        return f"Error: material balls: {error}"


class BallProvider(QQuickImageProvider):
    def __init__(self, images: dict, lock):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._images, self._lock = images, lock

    def requestImage(self, id_, size, requested):  # noqa: N802 (Qt's name)
        with self._lock:
            return self._images.get(id_, QImage())


class MaterialBalls(QObject):
    updated = Signal()
    failed = Signal(str)

    def __init__(self, renderer=None, parent=None):
        super().__init__(parent)
        self._r, self._lock = renderer, threading.Lock()
        self._images: dict[str, QImage] = {}
        self._pending: dict[str, dict] = {}         # key -> values, waiting for the worker
        self._stamp = engine_stamp() if renderer is not None else ""
        self.provider = BallProvider(self._images, self._lock)

    def url(self, values: dict) -> str:
        if self._r is None:
            return ""
        values = ball_values(values)
        key = ball_key(values, self._stamp)
        with self._lock:
            if key in self._images:
                return f"image://ball/{key}"
            if key in self._pending:
                return ""
        disk = folder() / f"{key}.png"
        image = QImage(str(disk)) if disk.is_file() else QImage()
        with self._lock:
            if not image.isNull():
                self._images[key] = image
                return f"image://ball/{key}"
            first = not self._pending
            self._pending[key] = values
        if first:
            self._r.call(self._work)
        return ""

    def _work(self, eng):
        """On the viewport's thread: draw every waiting ball in one scene, keep them, say so (loudly on failure)."""
        with self._lock:
            batch, self._pending = self._pending, {}
        if not batch:
            return
        try:
            images = render_balls(eng, batch)
            for key, image in images.items():
                put_file(folder() / f"{key}.png", lambda tmp, im=image: _save(im, tmp), "material ball")
            with self._lock:
                self._images.update(images)
            _trim()
        except Exception as e:  # noqa: BLE001  reported, never a silent blank
            self.failed.emit(f"Error: material balls: {e}")
            return
        self.updated.emit()


def _save(image: QImage, tmp: Path):
    if not image.save(str(tmp), "PNG"):
        raise RuntimeError(f"could not write the material ball {tmp}")


def _trim():
    files = sorted(folder().glob("*.png"), key=lambda p: p.stat().st_mtime)
    for p in files[:-CAP] if len(files) > CAP else []:
        p.unlink(missing_ok=True)
