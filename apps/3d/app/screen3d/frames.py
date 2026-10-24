"""The viewport picture: Storm frames (Cycles steps in the Final look) from the 3D engine's `view` request (ENGINE_CONTRACT.md § 4), off the GUI
thread, newest request wins (a view asked for while one renders replaces any waiting one). The newest picture is
served to QML as image://view/<serial>. The worker itself is the kit's (rostrum_gui.frames.PictureWorker); this
file is what is 3D's: the engine, the scene sent again only when it changed (`ensure_scene`), and picks.

Picks go through the same thread and engine, in the order asked, before the next view; each answer comes back as
`picked(item id, reply)` ("" = nothing there).
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
    ready = Signal(int, float, bool, bool, object)  # serial of the newest picture, its time in ms, whether the scene's
    #   dome lit it, whether the camera looked through has depth of field, and the Final look's progress and the card's
    #   memory ({"final": … or None, "vram": …}, ENGINE_CONTRACT.md § 4)
    picked = Signal(str, object)  # item id under the click ("" for empty space), and the engine's whole reply (point,
    #   normal: where the surface was hit and which way it faces)
    notice = Signal(str)         # the engine was started again (never silent)

    def __init__(self, parent=None):
        super().__init__("view3d", parent)
        self._final = False                          # the last view was the Final look (Cycles), worker thread only
        self.start()

    def request(self, scene: dict, req: dict):
        """Draw `req` (Engine.view's fields) of `scene`; replaces a view still waiting."""
        self.post_latest(("view", scene, req))

    def pick(self, scene: dict, req: dict):
        """What is at req's x, y (Engine.pick's fields); answered by `picked`."""
        self.post_ordered(("pick", scene, req))

    def call(self, fn):
        """Run `fn(engine)` on this thread and engine, in order with picks and never dropped (material balls). `fn`
        reports its own failures; the next view sends the viewport's scene again (ensure_scene)."""
        self.post_ordered(("call", fn, {}))

    def open_engine(self):
        return open_engine()

    def handle(self, eng, job):
        kind, scene, req = job
        if kind == "call":
            return scene(eng)
        if sys.platform != "win32":
            raise RuntimeError("the live viewport reads the engine's shared memory, Windows only for now")
        final = req.get("renderer") == "cycles"
        if kind == "view" and self._final and not final:                # leaving the Final look: a fresh engine, the card's memory back
            eng.release()
        if kind == "view":
            self._final = final
        eng.ensure_scene(scene)
        if kind == "pick":
            out = eng.pick(**req)
            self.picked.emit(out.get("item", "") if out.get("hit") else "", out)
        else:
            *pixels, reply = eng.view(**req)
            image = image_from_pixels(*pixels)
            if image.isNull():
                raise RuntimeError("the engine's picture could not be read from its shared memory")
            self.ready.emit(self.publish(image), float(reply.get("ms", 0.0)), bool(reply.get("sceneDome", False)),
                            bool(reply.get("cameraDof", False)),
                            {"final": reply.get("final"), "vram": reply.get("vram")})
        for line in eng.take_notices():
            self.notice.emit(line)

    def describe(self, job, error):
        return f"Error: viewport {job[0]} at frame {job[2].get('frame')}: {error}"
