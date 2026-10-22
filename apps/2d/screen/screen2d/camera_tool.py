"""The Camera tool (C): drag on the canvas to pan the camera, Alt+drag to push in or out (backend.cameraTool).

It writes the camera layer's own fields, `x` and `y` (where it looks) and `zoom`, the way any edit does (route.value_call:
a still field changes, an animated one gets a key at the playhead), so an agent does the same with `value.set` / `key.add`
on the camera layer. A drag is one gesture = one undo step (drags.py `_begin`). Dragging the picture right moves the
camera left: a layer on the camera's plane follows the pointer. Alt+drag up pushes in; a quarter of the frame's height
doubles the zoom. The tool is there only while the scene has a camera (rule of individuality). Coordinates are composition px.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d.evaluate import resolve
from rostrum2d.retime import END_OF_COMP

from . import route

DOUBLES_PER_QUARTER = 1.0       # the zoom doubles for each quarter of the frame's height dragged


@dataclass
class Grab:
    camera: str
    x: float
    y: float
    zoom: float


def active_camera(comp: dict, t: float) -> dict | None:
    """The camera showing at composition time t (the one later in the list wins, CAMERA.md), else the first camera."""
    cams = [c for c in comp.get("layers", []) if c["type"] == "camera"]
    shown = [c for c in cams if c.get("start", 0.0) <= t < c.get("end", END_OF_COMP)]
    return shown[-1] if shown else (cams[0] if cams else None)


class CameraTool(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b = bridge
        for sig in (bridge.docChanged, bridge.outlineChanged):
            sig.connect(self.changed)

    @Property(bool, notify=changed)
    def available(self) -> bool:
        """The scene has a camera: only then is the tool offered."""
        return any(c["type"] == "camera" for c in self.b.comp().get("layers", []))

    @Slot(result=bool)
    def begin(self) -> bool:
        cam = active_camera(self.b.comp(), self.b._t)
        if cam is None:
            self.b._fail("Error: camera: this scene has no camera; + Add › Camera first.")
            return False
        if cam.get("locked"):
            self.b._fail("Error: the camera is locked; unlock it to move it.")
            return False
        p = resolve(cam, self.b.own_t(cam["id"]))
        return self.b._begin("Move the camera", Grab(cam["id"], p["x"], p["y"], p["zoom"]))

    @Slot(float, float, bool)
    def drag(self, dx: float, dy: float, push: bool):
        """The pointer's total offset from the press, composition px; `push` (Alt): zoom instead of pan."""
        g = self.b._grab
        if self.b._drag is None or not isinstance(g, Grab):
            return
        item, t = self.b.doc.item(g.camera), self.b.own_t(g.camera)
        if push:
            zoom = max(0.01, g.zoom * 2 ** (-dy / (self.b.comp()["height"] / 4) * DOUBLES_PER_QUARTER))
            values = {"zoom": round(zoom, 4)}
        else:
            values = {"x": round(g.x - dx / g.zoom, 2), "y": round(g.y - dy / g.zoom, 2)}
        self.b._guard(lambda: self.b._drag.preview([route.value_call(item, k, v, t) for k, v in values.items()]))
