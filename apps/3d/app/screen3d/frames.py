"""The viewport picture: Storm frames (Cycles steps in the Final look) from the 3D engine's `view` request (ENGINE_CONTRACT.md § 4), off the GUI
thread, newest request wins (a view asked for while one renders replaces any waiting one). The newest picture is
served to QML as image://view/<serial>. The worker itself is the kit's (rostrum_gui.frames.PictureWorker); this
file is what is 3D's: the engine, the scene sent again only when it changed (`ensure_scene`), and picks.

Picks go through the same thread and engine, in the order asked, before the next view; each answer comes back as
`picked(item id, reply)` ("" = nothing there).

With a `link` (view_item.py) the window draws the live view itself: the quick look's views, picks and clay strokes go
to the Rostrum3DView item and its pictures land on screen without passing through here (`ready` still says so); the
Final look and the engine-only requests go to the engine program as before.
"""
from __future__ import annotations

import sys
import threading

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

    def __init__(self, parent=None, link=None):
        super().__init__("view3d", parent)
        self._final = False                          # the last view was the Final look (Cycles), worker thread only
        self.link = link                             # the window's own view (view_item.ViewLink), or None: pictures
        if link is not None:
            link.drawn.connect(self._drawn)
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

    def wait_for(self, fn, timeout=60.0):
        """`fn(engine)` on this thread, waited for (an operation that needs the engine: mesh.edit's geometry)."""
        box, done = {}, threading.Event()

        def go(eng):
            try:
                box["v"] = fn(eng)
            except Exception as e:  # noqa: BLE001  handed back to the caller, who raises it
                box["e"] = e
            finally:
                done.set()
        self.call(go)
        if not done.wait(timeout):
            raise RuntimeError(f"the engine did not answer in {timeout:.0f} s")
        if "e" in box:
            raise box["e"]
        return box["v"]

    def open_engine(self):
        if self.link is not None:
            from .view_item import ItemEngine
            return ItemEngine(self.link, open_engine())
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
        if kind == "view" and self.link is not None and not final:
            eng.show(req)                            # drawn in the window; `_drawn` says when
        elif kind == "pick":
            out = eng.pick(**req)
            self.picked.emit(out.get("item", "") if out.get("hit") else "", out)
        else:
            self.show(*eng.view(**req))
        for line in eng.take_notices():
            self.notice.emit(line)

    def show(self, view, width, height, stride, reply, trace=None) -> int:
        """A picture the engine drew (a view, or the one a sculpt event drew with its dab) as the newest one; its
        serial. `trace`: a dab_trace record, given the copy's times."""
        from . import dab_trace
        if trace is not None:
            trace["tCopy0"] = dab_trace.now()
        image = image_from_pixels(view, width, height, stride)
        if image.isNull():
            raise RuntimeError("the engine's picture could not be read from its shared memory")
        serial = self.publish(image)
        if trace is not None:
            trace["tCopy1"] = dab_trace.now()
        self.ready.emit(serial, float(reply.get("ms", 0.0)), bool(reply.get("sceneDome", False)),
                        bool(reply.get("cameraDof", False)),
                        {"final": reply.get("final"), "vram": reply.get("vram")})
        return serial

    def _drawn(self, reply: dict):
        """The window drew a picture (view_item.ViewLink.drawn): as `show`'s `ready`, with no picture to serve."""
        if not reply.get("ok", True):
            return self.failed.emit(f"Error: viewport view: {reply.get('error', 'no reason given')}")
        self.serial += 1
        self.ready.emit(self.serial, float(reply.get("tRender1", 0.0)) - float(reply.get("tRender0", 0.0)),
                        bool(reply.get("sceneDome", False)), bool(reply.get("cameraDof", False)),
                        {"final": None, "vram": reply.get("vram"), "frame": reply.get("frame")})

    def describe(self, job, error):
        return f"Error: viewport {job[0]} at frame {job[2].get('frame')}: {error}"


class EngineVia:
    """The viewport's engine as mesh.edit and mesh.unfold ask for it (ops_mesh.use_engine): each call waited for on its thread."""

    def __init__(self, worker):
        self.worker = worker

    def ensure_scene(self, scene):
        return self.worker.wait_for(lambda e: e.ensure_scene(scene))

    def geometry(self, item):
        return self.worker.wait_for(lambda e: e.geometry(item))

    def unfold(self, item, size):
        return self.worker.wait_for(lambda e: e.unfold(item, size))
