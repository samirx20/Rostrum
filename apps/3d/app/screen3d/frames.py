"""The viewport picture: Storm frames from the 3D engine's `view` request (ENGINE_CONTRACT.md § 4), off the GUI
thread, newest request wins (a view asked for while one renders replaces any waiting one; stale views are never
queued). The newest picture is served to QML as image://view/<serial>.

One worker thread owns one long-lived engine process (rostrum3d.engine.Engine); `close` ends it. Before each view
the scene is sent again only when it changed (`ensure_scene`). Picks go through the same thread and engine, in the
order asked, before the next view; each answer comes back as `picked(item id)` ("" = nothing there).
A failed view or pick is reported (`failed`), never shown as if it worked; the next request tries again.
"""
from __future__ import annotations

import sys
import threading
from collections import deque

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider


def open_engine():
    """The engine the viewport uses (swap here, nowhere else)."""
    from rostrum3d.engine import Engine
    return Engine()


class ViewProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._lock, self._image = threading.Lock(), QImage()

    def put(self, image: QImage):
        with self._lock:
            self._image = image

    def requestImage(self, id_, size, requested):  # noqa: N802 (Qt's name)
        with self._lock:
            return self._image


def _picture(eng, req: dict) -> tuple[QImage, dict]:
    view, w, h, stride, reply = eng.view(**req)
    try:
        image = QImage(view, w, h, stride, QImage.Format.Format_RGBA8888).copy()   # copied: the slot is reused
    finally:
        view.release()
    return image, reply


class ViewRenderer(QObject):
    ready = Signal(int, float)   # serial of the newest picture, its time in ms
    picked = Signal(str)         # item id under the click, "" for empty space
    failed = Signal(str)
    notice = Signal(str)         # the engine was started again (never silent)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.provider = ViewProvider()
        self._cv = threading.Condition()
        self._view, self._picks, self._stop, self._serial = None, deque(), False, 0
        self._thread = threading.Thread(target=self._run, name="view3d", daemon=True)
        self._thread.start()

    def request(self, scene: dict, req: dict):
        """Draw `req` (Engine.view's fields) of `scene`; replaces a view still waiting."""
        with self._cv:
            self._view = (scene, req)
            self._cv.notify()

    def pick(self, scene: dict, req: dict):
        """What is at req's x, y (Engine.pick's fields); answered by `picked`."""
        with self._cv:
            self._picks.append((scene, req))
            self._cv.notify()

    def _next(self):
        with self._cv:
            while self._view is None and not self._picks and not self._stop:
                self._cv.wait()
            if self._stop:
                return None
            if self._picks:
                return ("pick", *self._picks.popleft())
            job, self._view = ("view", *self._view), None
            return job

    def _run(self):
        eng = None
        try:
            while (job := self._next()) is not None:
                kind, scene, req = job
                try:
                    if sys.platform != "win32":
                        raise RuntimeError("the live viewport reads the engine's shared memory, Windows only for now")
                    eng = eng or open_engine()
                    eng.ensure_scene(scene)
                    if kind == "pick":
                        out = eng.pick(**req)
                        self.picked.emit(out.get("item", "") if out.get("hit") else "")
                    else:
                        image, reply = _picture(eng, req)
                        if image.isNull():
                            raise RuntimeError("the engine's picture could not be read from its shared memory")
                        self.provider.put(image)
                        self._serial += 1
                        self.ready.emit(self._serial, float(reply.get("ms", 0.0)))
                    for line in eng.take_notices():
                        self.notice.emit(line)
                except Exception as e:  # noqa: BLE001  any failure is reported, loudly
                    line = f"Error: viewport {kind} at frame {req.get('frame')}: {e}"
                    print(line, file=sys.stderr)
                    self.failed.emit(line)
        finally:
            if eng is not None:
                eng.close()

    def close(self):
        with self._cv:
            self._stop = True
            self._cv.notify()
        self._thread.join(timeout=15)
