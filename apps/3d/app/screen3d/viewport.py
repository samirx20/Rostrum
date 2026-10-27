"""The live 3D viewport, for QML as `viewport`: the camera (viewcam.ViewCam), the viewport-only light settings and
the picture (frames.ViewRenderer, image://view/<serial>). Everything here is screen state: orbiting, exposure or
the studio light never touch the document or its history. Clicking picks through the engine and selects the item
(empty space selects nothing, as clicking the empty 2D canvas selects the composition).

It starts looking through the shot camera; orbiting, panning or zooming there switches to the free camera from
the shot camera's view. Look: Final (Shift+F, final_look.py) draws progressive Cycles in place with the Render button's
settings; any change starts it over, and while the Render button's own render runs it waits (one Cycles on the card).
With a panel, bulb or sun light selected it can look through that light (to aim it by eye),
following the light while it moves; moving the view there continues freely from it (the light stays where it is). It draws again when the document, the playhead frame or the selection changes.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication

from rostrum3d import aim, ops_mesh, through

from . import dab_trace, placing, shot_frame
from .gizmo import View
from .final_look import NEXT_MS, FinalLook
from .render_job import cycles_of
from .frames import EngineVia, ViewRenderer
from . import view_item
from .view_item import ViewLink
from .viewcam import ViewCam

MAX_WIDTH = 1600             # pictures wider than this are drawn smaller and scaled up on screen


_ENGINE_FOR_OPS = [None]          # the viewport whose engine mesh.edit uses (one window at a time)


def scene_ids(scene: dict) -> set[str]:
    out, stack = set(), list(scene.get("items", []))
    while stack:
        node = stack.pop()
        out.add(node["id"])
        stack += node.get("children", []) if node["type"] != "combine" else []    # a combine's inputs aren't drawn
    return out


class Viewport(QObject):
    serialChanged = Signal()
    settingsChanged = Signal()
    statusChanged = Signal()
    picked = Signal(str)             # a click's answer (the item under it, "" for none): the right-click menu opens on it

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.bridge, self.cam = bridge, ViewCam()
        self.link = ViewLink(self) if view_item.on() else None   # the window draws the live view (view_item.py)
        self._r = ViewRenderer(self, link=self.link)
        self.provider = self._r.provider
        self._serial, self._ms, self._status, self._picture = 0, 0.0, "", 0
        self._exposure, self._studio, self._lights = 0.0, 1.0, True
        self._dome = False                           # the engine said the scene's own dome lit the last picture
        self._ao_on, self._ao, self._dof = True, 1.0, True    # contact shading (on, strength) and depth of field
        self._cam_dof = False                        # the engine said the camera looked through has depth of field on
        self._size, self._scale = None, 1.0          # request size (picture pixels); picture px per screen px
        self._scene, self._shot, self._started = None, None, False
        self._wide, self._frame = None, (0.0, 0.0, 1.0, 1.0)  # the scene with the wider shot camera; the frame (0..1)
        self._dim = True                             # dim the scene outside the shot frame (screen state)
        self.final = FinalLook()
        self._next = QTimer(self, singleShot=True, interval=NEXT_MS, timeout=self.redraw)   # the next Final step
        self._r.ready.connect(self._on_ready)
        if self.link is not None:
            self.link.shown.connect(dab_trace.shown)
        self._r.picked.connect(self._on_picked)
        self._r.failed.connect(self._on_failed)
        self._r.notice.connect(self._set_status)
        bridge.docChanged.connect(self._on_doc)
        bridge.shotChanged.connect(self._on_shot)
        bridge.frameChanged.connect(self.redraw)
        bridge.selectionChanged.connect(self.redraw)
        bridge.selectionChanged.connect(lambda *_: self.settingsChanged.emit())   # canThroughLight follows it
        bridge.render.changed.connect(self._on_render_job)     # Final waits while the Render button renders
        from .gizmo_qt import Gizmo
        from .mesh_edit_qt import MeshEdit
        self.mesh_edit = MeshEdit(bridge, self)                # Edit mesh: points / edges / faces (mesh_edit_qt.py)
        from .paint_mode_qt import PaintMode
        self.paint = PaintMode(bridge, self)                   # Paint (B): brush strokes on a mesh (paint_mode_qt.py)
        from .clay_tool_qt import ClayTool
        self.clay_tool = ClayTool(bridge, self)                # Clay (Q): Lump and the brushes (clay_tool_qt.py)
        self.gizmo = Gizmo(bridge, self)                       # the selected item's handles (gizmo_qt.py)
        ops_mesh.use_engine(EngineVia(self._r), bridge.doc.folder)   # mesh.edit asks this engine for a shape's mesh
        _ENGINE_FOR_OPS[0] = self                              # (the newest window's; an old one closing leaves it)
        from .place_light import PlaceLight
        self.place = PlaceLight(self)                          # lights placed by highlight, linked by clicking
        from .focus_pick import FocusPick
        self.focus = FocusPick(self)                           # a camera's focus set by clicking (focus_pick.py)
        from .onion_qt import Onion
        self.onion = Onion(self)                               # onion skin: ghosts at other frames (onion_qt.py)
        from .bones_qt import Bones
        self.bone_tool = Bones(self)                           # Bones: place a chain by clicking, see it (bones_qt.py)

    # --- QML properties
    serial = Property(int, lambda s: s._serial, notify=serialChanged)
    pictureSerial = Property(int, lambda s: s._picture, notify=serialChanged)   # the newest engine picture (image://view)
    # the live view is drawn in the window (LiveView.qml), not served as pictures; the Final look stays a picture
    inWindow = Property(bool, lambda s: s.link is not None, constant=True)
    viewLink = Property(QObject, lambda s: s.link, constant=True)
    ms = Property(float, lambda s: s._ms, notify=serialChanged)
    status = Property(str, lambda s: s._status, notify=statusChanged)
    mode = Property(str, lambda s: s.cam.mode, notify=settingsChanged)
    hasShot = Property(bool, lambda s: bool(s.cam.camera), notify=settingsChanged)
    # the selection is a light that can be looked through (rect, disk, strip, sphere, distant), or we already are
    canThroughLight = Property(bool, lambda s: s.cam.mode == "light" or s._selected_light() != "", notify=settingsChanged)
    throughLight = Property(str, lambda s: s.cam.light if s.cam.mode == "light" else "", notify=settingsChanged)
    exposure = Property(float, lambda s: s._exposure, notify=settingsChanged)
    studio = Property(float, lambda s: s._studio, notify=settingsChanged)
    sceneLights = Property(bool, lambda s: s._lights, notify=settingsChanged)
    # the studio light is only used when the scene's own dome isn't (the engine says which, per picture)
    studioInUse = Property(bool, lambda s: not s._dome, notify=settingsChanged)
    aoOn = Property(bool, lambda s: s._ao_on, notify=settingsChanged)
    aoStrength = Property(float, lambda s: s._ao, notify=settingsChanged)
    dof = Property(bool, lambda s: s._dof, notify=settingsChanged)
    # depth of field only matters when the camera looked through has it on (the engine says which, per picture)
    cameraDof = Property(bool, lambda s: s._cam_dof, notify=settingsChanged)
    look = Property(str, lambda s: "final" if s.final.on else "quick", notify=settingsChanged)
    finalLine = Property(str, lambda s: s.final.line, notify=serialChanged)
    finalFraction = Property(float, lambda s: s.final.fraction, notify=serialChanged)
    dim = Property(bool, lambda s: s._dim, notify=settingsChanged)
    # the shot frame in the viewport, as parts of its width and height [x, y, w, h]; shown in the shot camera only
    frameRect = Property("QVariantList", lambda s: list(s._frame), notify=settingsChanged)
    onionSkin = Property(QObject, lambda s: s.onion, constant=True)
    clay = Property(QObject, lambda s: s.clay_tool, constant=True)        # QML: viewport.clay (clay_tool_qt.py)
    bones = Property(QObject, lambda s: s.bone_tool, constant=True)       # QML: viewport.bones (bones_qt.py)     # QML: viewport.onionSkin (onion_qt.py)

    # --- the scene and the shot (compiled once per document change, not per mouse move)
    def _on_doc(self, *_):
        self._scene = self._shot = self._wide = None
        self.redraw()

    def _on_shot(self):
        """Another shot is shown: look through its camera, its frame size."""
        self.cam.camera, self._started = "", False
        self._on_doc()

    def _compiled(self):
        if self._scene is None:
            self._shot, self._scene = self.bridge.shot_info(), self.bridge.scene()
            if self.cam.camera and self.cam.camera != self._shot["camera"]:
                self.cam.camera = ""                 # the shot's camera changed: start from the new one
                self._started = False
            if not self._started:
                self._home()
                self.cam.mode, self._started = "shot", True
                self.settingsChanged.emit()
        return self._scene

    def _fit(self):
        """The shot frame for this viewport size, and the scene with the shot camera made that much wider."""
        w, h = self._size
        dpr = QGuiApplication.primaryScreen().devicePixelRatio() if QGuiApplication.primaryScreen() else 1.0
        x, y, fw, fh = shot_frame.fit(w, h, self._shot["width"], self._shot["height"], shot_frame.MARGIN * dpr * self._scale)
        frame = (x / w, y / h, fw / w, fh / h)
        if frame != self._frame:
            self._frame = frame
            self.settingsChanged.emit()
        self._wide = shot_frame.overscan(self._scene, self._shot["camera"], w / fw, w / h)

    def sent(self) -> tuple[dict, dict]:
        """(scene, camera part) as the engine gets them: through the shot camera, its wider copy (shot_frame.py)."""
        scene, cam = self._compiled(), self.cam.request(self.bridge.frame, *self._size)
        if self.cam.mode != "shot":
            return scene, cam
        if self._wide is None:
            self._fit()
        return self._wide, {**cam, "camera": shot_frame.VIEW_CAMERA}

    def _home(self):
        w, h = self._size or (16, 9)
        self.cam.home(self._scene, self._shot["camera"], self.bridge.frame, w / h)

    def _leave_shot(self):
        """A camera move while looking through the shot camera or a light: continue freely from its view."""
        if self.cam.mode == "shot":
            self._home()
            self.settingsChanged.emit()
        elif self.cam.mode == "light":
            self.cam.mode = "free"
            self.settingsChanged.emit()

    def _selected_light(self) -> str:
        try:
            scene = self._compiled()
        except Exception:  # noqa: BLE001  no scene yet: nothing to look through (the draw says why)
            return ""
        sel = self.bridge.selected
        return sel if sel and through.aimable(scene, sel) else ""

    def _guard(self, fn) -> bool:
        try:
            fn()
            return True
        except Exception as e:  # noqa: BLE001  a viewport that can't draw says why, loudly
            self._set_status(f"Error: viewport: {e}")
            print(self._status, file=sys.stderr)
            return False

    def _request(self) -> dict:
        w, h, sel = *self._size, self.bridge.selected
        if self.cam.mode == "light":
            if through.aimable(self._scene, self.cam.light):
                self.cam.follow(self._scene, self.bridge.frame)             # the light may have moved
            else:                                                           # deleted, or no longer a panel or bulb
                self.cam.mode = "free"
                self.settingsChanged.emit()
        cam = self.sent()[1]
        if self.final.on:
            fw, fh = self.final.size((w, h))
            return {**cam, "width": fw, "height": fh, **self.final.fields(cycles_of(self.bridge.doc.data, self.bridge.shot_id, self.bridge.shot_info()))}
        drawn = scene_ids(self._scene)
        # Draw / Spin armed: the clay under the pointer (a drag from there joins it) gets the thin hover outline;
        # sent only when there is one (an older core refuses the field)
        hovered = [c for c in self.clay_tool.drawer.outlined() if c in drawn and c != sel]
        return {**cam, "renderer": "storm", "view": "",
                "exposure": self._exposure, "studio": self._studio, "sceneLights": self._lights,
                "ao": self._ao if self._ao_on else 0.0, "dof": self._dof,
                "selected": ([sel] if sel in drawn and not self.clay_tool.sculpting(sel) else []),  # a material or key
                #   has no outline; nor the clay being sculpted (the brush ring is its mark; CL1b: its outline doubled
                #   every picture's time while sculpting)
                **({"hovered": hovered} if hovered else {}),
                **self.onion.request(drawn)}                   # onion skin's ghosts, when on (quick look only)

    @Slot()
    def redraw(self):
        self._next.stop()
        if self.final.on and self.bridge.render.running():
            self.final.line = "Final waits for the render"
            return self.serialChanged.emit()
        if self._size is not None:
            self._guard(lambda: self._r.request(self.sent()[0], self._request()))

    # --- slots for QML
    @Slot(float, float)
    def setSize(self, w, h):
        """The viewport's size in device pixels; the picture is drawn at that size, at most MAX_WIDTH wide."""
        self._scale = min(1.0, MAX_WIDTH / max(w, 1.0))
        size = (max(16, round(w * self._scale)), max(16, round(h * self._scale)))
        if size != self._size:
            self._size, self._wide = size, None
            self.redraw()

    def _move(self, fn):
        if self._guard(lambda: (self._compiled(), self._leave_shot(), fn())):
            self.redraw()

    @Slot(float, float)
    def orbit(self, dx, dy):
        self._move(lambda: self.cam.orbit(dx, dy))

    @Slot(float, float)
    def pan(self, dx, dy):
        self._move(lambda: self.cam.pan(dx * self._scale, dy * self._scale, self._size[1]))

    @Slot(float)
    def zoom(self, steps):
        self._move(lambda: self.cam.zoom(steps))

    @Slot()
    def home(self):
        if self._guard(lambda: (self._compiled(), self._home())):
            self.settingsChanged.emit()
            self.redraw()

    @Slot(str)
    def setMode(self, m):
        """"free", "shot", or "light" (through the selected light)."""
        if m == "light":
            light = self._selected_light()
            if light and self._guard(lambda: self.cam.look_through(self._compiled(), light, self.bridge.frame)):
                self.settingsChanged.emit()
                self.redraw()
            return
        if m != self.cam.mode and self._guard(lambda: (self._compiled(), self.cam.set_mode(m))):
            self.settingsChanged.emit()
            self.redraw()

    @Slot(str)
    def setLook(self, look):
        """"quick" (Storm) or "final" (progressive Cycles with the Render button's settings)."""
        if (look == "final") != self.final.on:
            self.final.start() if look == "final" else self.final.stop()
            self.settingsChanged.emit()
            self.serialChanged.emit()
            self.redraw()

    @Slot()
    def toggleLook(self):
        self.setLook("quick" if self.final.on else "final")

    def _on_render_job(self):
        if self.final.on and not self.bridge.render.running() and self.final.line.startswith("Final waits"):
            self.redraw()

    def _setting(self, name, value):
        if getattr(self, name) != value:
            setattr(self, name, value)
            self.settingsChanged.emit()
            self.redraw()

    @Slot(bool)
    def setDim(self, b):
        self._setting("_dim", bool(b))

    @Slot(float)
    def setExposure(self, v):
        self._setting("_exposure", max(-4.0, min(4.0, float(v))))

    @Slot(float)
    def setStudio(self, v):
        self._setting("_studio", max(0.0, min(2.0, float(v))))

    @Slot(bool)
    def setSceneLights(self, b):
        self._setting("_lights", bool(b))

    @Slot(bool)
    def setAoOn(self, b):
        self._setting("_ao_on", bool(b))

    @Slot(float)
    def setAoStrength(self, v):
        self._setting("_ao", max(0.05, min(2.0, float(v))))

    @Slot(bool)
    def setDof(self, b):
        self._setting("_dof", bool(b))

    @Slot(float, float)
    def click(self, x, y):
        """A click at (x, y) device pixels: select what is there, or place the shape the Shapes flyout armed there (placing
        or linking a light: that instead)."""
        if self._size is not None and self.focus.wants_click():
            self._guard(lambda: self.focus.click(x, y))
        elif self._size is not None and self.place.wants_click():
            self._guard(lambda: self.place.click(x, y))
        elif self._size is not None and self.clay_tool.wants_click():          # Clay's Lump: a ball there
            self._guard(lambda: self.clay_tool.click(x, y))
        elif self._size is not None and self.bone_tool.wants_click():
            self._guard(lambda: self.bone_tool.click(x, y))
        elif self._size is not None:      # a drawn bone near the click is picked before the mesh behind it (bones_qt.py)
            bone = "" if getattr(self, "_drop", "") or self.bridge.add.armed else self.bone_tool.bone_at(x, y)
            self._guard(lambda: self._on_picked(bone) if bone else self._r.pick(*self._pick_at(x, y)))

    @Slot(float, float)
    def altClick(self, x, y):
        """Alt+click at (x, y) device pixels: the selected light's highlight lands there (picking a camera's focus: the
        focus follows the item clicked)."""
        if self._size is not None and self.focus.wants_click():
            self._guard(lambda: self.focus.click(x, y, on_item=True))
        elif self._size is not None:
            self._guard(lambda: self.place.alt_click(x, y))

    def _pick_at(self, x, y):
        scene, cam = self.sent()
        req = {**cam, "x": round(x * self._scale), "y": round(y * self._scale)}
        self._last_pick, self._last_click = (scene, req), [x, y]
        return scene, req

    @Slot(str, float, float)
    def dropMaterial(self, material_id, x, y):
        """A material dropped at (x, y) device pixels: the item there gets it (picked like a click, never selected)."""
        self._drop = material_id
        self.click(x, y)

    def picture(self):
        """The viewport's picture as on screen now (a QImage): the window's own view grabbed from the window, else the
        newest engine picture."""
        item = self.link.item if self.link is not None else None
        if item is None or self.final.on:
            return self.provider.requestImage("", None, None)
        from PySide6.QtCore import QPointF, QRectF
        win = item.window()
        dpr = win.devicePixelRatio()
        top = item.mapToScene(QPointF(0, 0))
        r = QRectF(top.x() * dpr, top.y() * dpr, item.width() * dpr, item.height() * dpr).toRect()
        return win.grabWindow().copy(r)

    def close(self):
        if _ENGINE_FOR_OPS[0] is self:
            ops_mesh.use_engine(None)
            _ENGINE_FOR_OPS[0] = None
        self._next.stop()
        self._r.close()

    # --- answers from the worker
    def _on_ready(self, serial, ms, dome, cam_dof=False, extra=None):
        self._serial, self._ms = serial, ms
        if (extra or {}).get("frame") is None:              # an engine picture, not a frame of the window's own view
            self._picture = serial
        dab_trace.ready(serial)                          # (nothing unless tools/clay_hops.py traces dabs)
        if self.final.on and (extra or {}).get("final") is not None:
            step = self.final.take(extra)
            if step == "leave":
                line = self.final.line
                self.setLook("quick")
                return self._set_status(line)
            if step in ("next", "smaller"):
                self._next.start()
        if dome != self._dome or cam_dof != self._cam_dof:
            self._dome, self._cam_dof = dome, cam_dof
            self.settingsChanged.emit()
        self._set_status("")                         # a picture came: the last failure or restart notice is over
        self.bridge.engine_said("")
        self.serialChanged.emit()

    def _on_failed(self, line):
        self.bridge.engine_said(line)                # a bevel too big: the panel offers the largest that fits
        if self.final.on:                            # Cycles could not go on: back to Quick, and the line says why
            self.setLook("quick")
            line = f"{line}  ·  Final stopped, back to Quick"
        self._set_status(line)

    def _on_picked(self, item, reply=None):
        drop, self._drop = getattr(self, "_drop", ""), ""
        if drop:
            return self.bridge.mats.dropOn(drop, item)
        if self.bridge.add.armed:
            return self._guard(lambda: self._place(item, reply or {}))
        if item != self.bridge.selected:
            self.bridge.select(item)
        self.picked.emit(item or "")

    def _place(self, item, reply):
        """The armed shape onto the surface the click hit (the engine's point and normal), else onto the ground."""
        scene, req = self._last_pick
        # the shot camera's place (an outline turns its front to it) and the click (where typing shows its cursor)
        where = {"eye": aim.point(through.find_item(self._compiled(), self._shot["camera"], self.bridge.frame)[0], [0, 0, 0]),
                 "px": self._last_click}
        if item:
            on = through.find_item(scene, item, self.bridge.frame)
            return self.bridge.add.place_at({"point": reply["point"], "normal": reply["normal"], "item": item, **where},
                                            (on[0], on[1]))
        view = View.of(req, scene, self.bridge.frame, req["width"], req["height"])
        hit = placing.ground_hit(view, req["x"], req["y"])
        if hit is None:
            return self.bridge.fail_line("Error: place: that click is above the ground and on nothing; click a surface.")
        self.bridge.add.place_at({"point": hit[0], "normal": hit[1], **where}, None)

    def _set_status(self, text):
        if text != self._status:
            self._status = text
            self.statusChanged.emit()
