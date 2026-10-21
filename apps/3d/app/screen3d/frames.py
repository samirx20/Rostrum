"""The viewport picture: Storm frames from the 3D engine's `view` request (ENGINE_CONTRACT.md § 4), off the GUI
thread, newest request wins (a view asked for while one renders replaces any waiting one). The newest picture is
served to QML as image://view/<serial>. The worker itself is the kit's (rostrum_gui.frames.PictureWorker); this
file is what is 3D's: the engine, the scene sent again only when it changed (`ensure_scene`), and picks.

Picks go through the same thread and engine, in the order asked, before the next view; each answer comes back as
`picked(item id)` ("" = nothing there).
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Signal
from rostrum_gui.frames import ImageProvider, PictureWorker, image_from_pixels

ViewProvider = ImageProvider


def open_engine():
    """The engine the viewport uses (swap here, nowhere else)."""
    from rostrum3d.engine import Engine
    return Engine()


class ViewRenderer(PictureWorker):
    ready = Signal(int, float, bool)  # serial of the newest picture, its time in ms, whether the scene's dome lit it
    picked = Signal(str)         # item id under the click, "" for empty space
    notice = Signal(str)         # the engine was started again (never silent)

    def __init__(self, parent=None):
        super().__init__("view3d", parent)
        self.start()

    def request(self, scene: dict, req: dict):
        """Draw `req` (Engine.view's fields) of `scene`; replaces a view still waiting."""
        self.post_latest(("view", scene, req))

    def pick(self, scene: dict, req: dict):
        """What is at req's x, y (Engine.pick's fields); answered by `picked`."""
        self.post_ordered(("pick", scene, req))

    def open_engine(self):
        return open_engine()

    def handle(self, eng, job):
        kind, scene, req = job
        if sys.platform != "win32":
            raise RuntimeError("the live viewport reads the engine's shared memory, Windows only for now")
        eng.ensure_scene(scene)
        if kind == "pick":
            out = eng.pick(**req)
            self.picked.emit(out.get("item", "") if out.get("hit") else "")
        else:
            *pixels, reply = eng.view(**req)
            image = image_from_pixels(*pixels)
            if image.isNull():
                raise RuntimeError("the engine's picture could not be read from its shared memory")
            self.ready.emit(self.publish(image), float(reply.get("ms", 0.0)), bool(reply.get("sceneDome", False)))
        for line in eng.take_notices():
            self.notice.emit(line)

    def describe(self, job, error):
        return f"Error: viewport {job[0]} at frame {job[2].get('frame')}: {error}"
