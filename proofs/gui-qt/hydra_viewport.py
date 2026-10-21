"""USD's Hydra viewport in the GLViewport slot (README › Hydra in the window).

`HydraViewport` is a QQuickFramebufferObject like `viewport.GLViewport`, with the same `time` and `tint`
properties, so QML uses it unchanged. Its renderer creates a `UsdImagingGL.Engine` on Qt's render thread (where
Qt's GL context is current), and each frame calls `engine.Render()`; HgiInterop composites Storm's result into
the framebuffer Qt has bound. Mouse: left drag orbit, middle drag (or Shift + left) pan, wheel / right drag zoom,
click picks the prim under the cursor. `time` turns the view slowly (the Turn speed slider), like the GL test scene.

Needs the bundle's Python 3.13 USD bindings: `load_usd(bundle)` puts them on the path (read-only, no .pyc written).
"""
import glob
import math
import os
import sys

from PySide6.QtCore import Property, QPointF, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickFramebufferObject, QQuickOpenGLUtils

Usd = UsdGeom = UsdImagingGL = Gf = Glf = CameraUtil = None


def load_usd(bundle, plugin_paths=()):
    """Import pxr from Blender's Windows library bundle (OpenUSD built with Hydra and Python 3.13)."""
    global Usd, UsdGeom, UsdImagingGL, Gf, Glf, CameraUtil
    sys.dont_write_bytecode = True  # the bundle belongs to another team: never write into it
    if plugin_paths:
        os.environ["PXR_PLUGINPATH_NAME"] = os.pathsep.join(plugin_paths)
    dirs = [os.path.join(bundle, "usd", "lib")] + sorted(glob.glob(os.path.join(bundle, "*", "bin")))
    dirs += [d for p in plugin_paths for d in (p, os.path.dirname(p))]  # a plug-in's own DLLs sit beside it
    for d in dirs:
        if not any(skip in d.lower() for skip in ("python", "ffmpeg")):  # our own Python; no GPL FFmpeg
            os.add_dll_directory(d)
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]  # USD loads plug-ins with plain LoadLibrary
    sys.path.insert(0, os.path.join(bundle, "usd", "lib", "python"))
    from pxr import CameraUtil, Gf, Glf, Usd, UsdGeom, UsdImagingGL  # noqa: F811
    globals().update(Usd=Usd, UsdGeom=UsdGeom, UsdImagingGL=UsdImagingGL, Gf=Gf, Glf=Glf, CameraUtil=CameraUtil)


class OrbitCamera:
    """Turntable camera around a centre, Y up, framed on the stage's bounds."""

    def __init__(self, stage):
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_, UsdGeom.Tokens.render])
        box = cache.ComputeWorldBound(stage.GetPseudoRoot()).ComputeAlignedRange()
        self.centre = Gf.Vec3d(box.GetMidpoint()) if not box.IsEmpty() else Gf.Vec3d(0)
        size = box.GetSize().GetLength() if not box.IsEmpty() else 10.0
        self.dist, self.yaw, self.pitch, self.fov = size * 1.1, 30.0, -18.0, 35.0
        self.near, self.far = size * 0.01, size * 20.0
        cams = [p for p in stage.Traverse() if p.IsA(UsdGeom.Camera)]
        if cams:  # start where the scene's first camera looks, orbiting its focus point
            gc = UsdGeom.Camera(cams[0]).GetCamera(Usd.TimeCode.Default())
            m = gc.transform
            pos, back = m.ExtractTranslation(), m.TransformDir(Gf.Vec3d(0, 0, 1)).GetNormalized()
            self.dist = gc.focusDistance or (pos - self.centre).GetLength()
            self.centre = pos - back * self.dist
            self.pitch = -math.degrees(math.asin(max(-1.0, min(1.0, back[1]))))
            self.yaw = math.degrees(math.atan2(back[0], back[2]))
            self.fov = gc.GetFieldOfView(Gf.Camera.FOVVertical)
        self.home = (Gf.Vec3d(self.centre), self.dist, self.yaw, self.pitch)

    def frustum(self, w, h, extra_yaw=0.0):
        rot = Gf.Rotation(Gf.Vec3d(1, 0, 0), self.pitch) * Gf.Rotation(Gf.Vec3d(0, 1, 0), self.yaw + extra_yaw)
        # camera-to-world: back off along z, turn, move to the centre
        cam = Gf.Matrix4d().SetTranslate(Gf.Vec3d(0, 0, self.dist)) * Gf.Matrix4d().SetRotate(rot) \
            * Gf.Matrix4d().SetTranslate(self.centre)
        f = Gf.Frustum()
        f.SetPositionAndRotationFromMatrix(cam)
        f.SetPerspective(self.fov, w / max(h, 1), self.near, self.far)
        return f

    def orbit(self, dx, dy):
        self.yaw -= dx * 0.3
        self.pitch = max(-89.0, min(89.0, self.pitch - dy * 0.3))

    def pan(self, dx, dy, h, f):
        scale = 2 * self.dist * math.tan(math.radians(self.fov / 2)) / max(h, 1)
        right, up = f.ComputeRightVector(), f.ComputeUpVector()
        self.centre -= right * dx * scale - up * dy * scale

    def zoom(self, steps):
        self.dist = max(self.near * 2, self.dist * (0.88 ** steps))


class HydraRenderer(QQuickFramebufferObject.Renderer):
    def __init__(self, item):
        super().__init__()
        self.engine, self.stage_path, self.time, self.info, self.ops = None, item.stagePath, 0.0, {}, []
        self.renderer_name, self.pick, self.lights = item.renderer, None, item.lights

    def synchronize(self, item):  # GUI thread is blocked: copy state across, hand results back
        self.time = item.time
        self.ops, item._ops = item._ops, []
        self.size = (item.width(), item.height())
        item.glInfo = self.info
        if self.pick is not None:
            item._set_picked(self.pick); self.pick = None
        if self.engine is not None and item.renderer != self.renderer_name:
            self.renderer_name = item.renderer
            self.engine.SetRendererPlugin(self.renderer_name)

    def _init(self):
        from OpenGL import GL
        self.stage = Usd.Stage.Open(self.stage_path)
        if not self.stage:
            raise RuntimeError(f"could not open USD stage {self.stage_path}")
        self.engine = UsdImagingGL.Engine()  # Hgi (HgiGL) is created on Qt's current GL context
        if self.renderer_name != "HdStormRendererPlugin":
            self.engine.SetRendererPlugin(self.renderer_name)
        self.camera = OrbitCamera(self.stage)
        self.params = UsdImagingGL.RenderParams()
        self.params.enableLighting = True
        self.params.enableSceneMaterials = True
        # "scene": the stage's own lights (Storm approximates area lights); "camera": usdview's default head light
        self.params.enableSceneLights = self.lights == "scene"
        self.params.colorCorrectionMode = "sRGB"
        self.params.clearColor = Gf.Vec4f(0.07, 0.072, 0.08, 1.0)
        self.info = {"vendor": GL.glGetString(GL.GL_VENDOR).decode(), "renderer": GL.glGetString(GL.GL_RENDERER).decode(),
                     "version": GL.glGetString(GL.GL_VERSION).decode(), "hydra": self.engine.GetCurrentRendererId(),
                     "stage": self.stage_path, "prims": sum(1 for _ in self.stage.Traverse())}

    def _apply(self, h, f):
        for op, *a in self.ops:
            if op == "orbit": self.camera.orbit(*a)
            elif op == "pan": self.camera.pan(*a, h, f)
            elif op == "zoom": self.camera.zoom(*a)
            elif op == "home": self.camera.centre, self.camera.dist, self.camera.yaw, self.camera.pitch = self.camera.home
            elif op == "pick": self._pick(*a)
        self.ops = []

    def _turn(self):  # the slow auto-turn; off for progressive renderers, which restart on every camera move
        return self.time * 6.0 if self.renderer_name == "HdStormRendererPlugin" else 0.0

    def _pick(self, x, y):
        w, h = self.fb_size
        # a 4-pixel frustum around the click (usdview's way), in normalised device coordinates
        f = self.camera.frustum(w, h, self._turn()).ComputeNarrowedFrustum(
            Gf.Vec2d(2 * x / w - 1, 1 - 2 * y / h), Gf.Vec2d(4.0 / w, 4.0 / h))
        hit = self.engine.TestIntersection(f.ComputeViewMatrix(), f.ComputeProjectionMatrix(),
                                           self.stage.GetPseudoRoot(), self.params)
        # (hit, point, normal, prim path, instancer path, instance index): the first Sdf.Path is the prim
        paths = [x for x in (hit or ()) if type(x).__name__ == "Path"]
        self.pick = str(paths[0]) if hit and hit[0] and paths else "(nothing)"

    def render(self):
        try:
            self._render()
        except Exception:  # fail loudly: a viewport that can't draw must stop the run, not show an empty frame
            import traceback
            traceback.print_exc()
            os._exit(3)

    def _render(self):
        if self.engine is None:
            self._init()
        fbo = self.framebufferObject()
        w, h = fbo.width(), fbo.height()
        self.fb_size = (w, h)
        self._apply(h, self.camera.frustum(w, h, self._turn()))
        f = self.camera.frustum(w, h, self._turn())
        self.engine.SetRenderBufferSize(Gf.Vec2i(w, h))
        self.engine.SetFraming(CameraUtil.Framing(Gf.Rect2i(Gf.Vec2i(0, 0), w, h)))
        self.engine.SetCameraState(f.ComputeViewMatrix(), f.ComputeProjectionMatrix())
        if self.lights == "camera":
            light = Glf.SimpleLight()  # a head light: sits at the camera and moves with it
            light.isCameraSpaceLight = True
            light.position = Gf.Vec4f(0, 0, 0, 1)
            light.ambient = Gf.Vec4f(0, 0, 0, 0)
            light.diffuse = light.specular = Gf.Vec4f(4, 4, 4, 1)  # Storm's PBR path needs more than 1.0 to read
            material = Glf.SimpleMaterial()
            material.specular, material.shininess = Gf.Vec4f(0.2, 0.2, 0.2, 1.0), 32.0
            self.engine.SetLightingState([light], material, Gf.Vec4f(0.35, 0.35, 0.35, 1.0))
        self.engine.Render(self.stage.GetPseudoRoot(), self.params)  # composites into Qt's bound FBO
        if not self.engine.IsConverged():
            self.update()  # progressive renderers (Cycles) keep refining
        QQuickOpenGLUtils.resetOpenGLState()


class HydraViewport(QQuickFramebufferObject):
    timeChanged, tintChanged, pickedChanged, rendererChanged = Signal(), Signal(), Signal(), Signal()
    stage_path = None  # set by main.py before QML loads
    renderer_name = "HdStormRendererPlugin"
    lights = "camera"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._time, self._tint, self._picked, self._ops, self.glInfo = 0.0, QColor("#c9ccd4"), "", [], {}
        self._renderer_id, self.stagePath = HydraViewport.renderer_name, HydraViewport.stage_path
        self.setMirrorVertically(True)  # GL's origin is bottom-left
        self.setAcceptedMouseButtons(Qt.AllButtons)
        self._last, self._moved = QPointF(), False

    def createRenderer(self):
        self._r = HydraRenderer(self)  # keep the Python wrapper alive; Qt owns and deletes the C++ side
        return self._r

    def _op(self, *op):
        self._ops.append(op); self.update()

    # ---- mouse: orbit / pan / zoom / pick (these become operations on the camera) ----
    def mousePressEvent(self, e):
        self._last, self._moved = e.position(), False
        e.accept()

    def mouseMoveEvent(self, e):
        d = e.position() - self._last
        self._last = e.position()
        self._moved = self._moved or abs(d.x()) + abs(d.y()) > 0
        b, shift = e.buttons(), bool(e.modifiers() & Qt.ShiftModifier)
        if b & Qt.MiddleButton or (b & Qt.LeftButton and shift): self._op("pan", d.x(), d.y())
        elif b & Qt.RightButton: self._op("zoom", -d.y() / 40.0)
        elif b & Qt.LeftButton: self._op("orbit", d.x(), d.y())

    def mouseReleaseEvent(self, e):
        if not self._moved and e.button() == Qt.LeftButton:
            dpr = self.window().devicePixelRatio() if self.window() else 1.0
            self._op("pick", e.position().x() * dpr, e.position().y() * dpr)

    def mouseDoubleClickEvent(self, e):
        self._op("home")

    def wheelEvent(self, e):
        self._op("zoom", e.angleDelta().y() / 120.0)

    def _set_picked(self, v):
        if v != self._picked:
            self._picked = v; self.pickedChanged.emit()
    picked = Property(str, lambda s: s._picked, notify=pickedChanged)

    def _get_renderer(self): return self._renderer_id
    def _set_renderer(self, v):
        if v != self._renderer_id:
            self._renderer_id = v; self.rendererChanged.emit(); self.update()
    renderer = Property(str, _get_renderer, _set_renderer, notify=rendererChanged)

    def _get_time(self): return self._time
    def _set_time(self, v):
        if v != self._time:
            self._time = v; self.timeChanged.emit(); self.update()
    time = Property(float, _get_time, _set_time, notify=timeChanged)

    def _get_tint(self): return self._tint
    def _set_tint(self, v): self._tint = QColor(v)  # the GL test scene's tint; the USD stage has its own materials
    tint = Property(QColor, _get_tint, _set_tint, notify=tintChanged)
