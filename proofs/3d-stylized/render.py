"""P-3D-3: render one USD stage through any Hydra renderer, chosen by name, to a PNG.

The stage is never changed: a look is a separate USD layer added to the session layer (light ramps
and other `rostrum:` attributes as overrides) plus a `/RostrumLook` prim whose `rostrum:*`
attributes go to the renderer as settings. Any USD/Hydra error fails the run (exit 1).

  .venv-usd\\Scripts\\python.exe -I render.py <stage.usda> <out.png> [--renderer rostrum|storm|cycles|<plugin id>]
      [--look looks\\painted.usda] [--width 1920 --height 1080] [--camera /World/Camera]
      [--frames 5]   (time this many extra frames after the first; reported as ms per frame)
      [--timeout 600] (progressive renderers: stop waiting after this many seconds, and fail)

GPU: the NVIDIA chip is asked for with SHIM_MCCOMPAT (set by render.ps1); the log says which ran.
"""
import argparse, ctypes, ctypes.wintypes as wt, glob, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.normpath(os.path.join(HERE, "..", "3d-product", ".build", "cycles", "lib", "windows_x64"))
PLUGINS = [os.path.join(HERE, ".build", "install"),
           os.path.normpath(os.path.join(HERE, "..", "3d-product", ".build", "cycles", "install", "hydra"))]
NAMES = {"rostrum": "HdRostrumPlugin", "storm": "HdStormRendererPlugin", "cycles": "HdCyclesPlugin"}


def load_usd():
    sys.dont_write_bytecode = True  # never write caches into the bundle
    os.environ["PXR_PLUGINPATH_NAME"] = os.pathsep.join(PLUGINS)
    dirs = [os.path.join(BUNDLE, "usd", "lib")] + sorted(glob.glob(os.path.join(BUNDLE, "*", "bin")))
    dirs += PLUGINS + [os.path.dirname(PLUGINS[1])]          # Cycles' own DLLs sit beside hydra\
    for d in dirs:
        if os.path.isdir(d) and not any(s in d.lower() for s in ("python", "ffmpeg")):  # no GPL FFmpeg
            os.add_dll_directory(d)
            os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]  # Hydra loads plug-ins with LoadLibrary
    sys.path.insert(0, os.path.join(BUNDLE, "usd", "lib", "python"))


def peak_ram_mb():
    class PMC(ctypes.Structure):
        _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD)] + [
            (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                           "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                           "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
    c = PMC(); c.cb = ctypes.sizeof(c)
    k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    k32.GetCurrentProcess.restype = wt.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]
    if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
        raise OSError("GetProcessMemoryInfo failed")
    return round(c.PeakWorkingSetSize / 2**20)


def look_settings(stage, prim_path="/RostrumLook"):
    prim = stage.GetPrimAtPath(prim_path)
    if not prim:
        return {}
    return {a.GetName(): a.Get() for a in prim.GetAttributes()
            if a.GetName().startswith("rostrum:") and a.HasAuthoredValue()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage"); ap.add_argument("out")
    ap.add_argument("--renderer", default="rostrum")
    ap.add_argument("--look", default=None)
    ap.add_argument("--width", type=int, default=1920); ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--camera", default=None)
    ap.add_argument("--frames", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=600)
    a = ap.parse_args()
    if not os.path.exists(a.stage):
        sys.exit(f"stage not found: {a.stage}")
    load_usd()
    from pxr import CameraUtil, Gf, Sdf, Tf, Usd, UsdGeom, UsdImagingGL
    from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext, QSurfaceFormat
    from PySide6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat

    fmt = QSurfaceFormat(); fmt.setVersion(4, 6); fmt.setProfile(QSurfaceFormat.CompatibilityProfile)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QGuiApplication([sys.argv[0], "-platform", "windows"])
    surface = QOffscreenSurface(); surface.setFormat(fmt); surface.create()
    ctx = QOpenGLContext(); ctx.setFormat(fmt)
    if not ctx.create() or not ctx.makeCurrent(surface):
        sys.exit("no OpenGL 4.6 context")
    gl = ctx.functions()
    gpu = f"{gl.glGetString(0x1F01)} / OpenGL {gl.glGetString(0x1F02)}"  # GL_RENDERER, GL_VERSION
    ffmt = QOpenGLFramebufferObjectFormat()
    ffmt.setAttachment(QOpenGLFramebufferObject.CombinedDepthStencil)
    fbo = QOpenGLFramebufferObject(a.width, a.height, ffmt)
    fbo.bind()
    # Hydra composites into this framebuffer with a depth test: it must start cleared (depth 1)
    gl.glClearColor(0, 0, 0, 1); gl.glClearDepthf(1.0); gl.glClear(0x4100)  # COLOR | DEPTH

    mark = Tf.Error.Mark()
    stage = Usd.Stage.Open(a.stage)
    if a.look:
        stage.GetSessionLayer().subLayerPaths.append(os.path.abspath(a.look))
    cam = a.camera or next((str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdGeom.Camera)), None)
    if not cam:
        sys.exit("the stage has no camera")
    engine = UsdImagingGL.Engine()
    plugin = NAMES.get(a.renderer, a.renderer)
    if plugin not in [str(p) for p in UsdImagingGL.Engine.GetRendererPlugins()] or not engine.SetRendererPlugin(plugin):
        sys.exit(f"renderer {plugin} not available; have {list(UsdImagingGL.Engine.GetRendererPlugins())}")
    settings = look_settings(stage)
    for k, v in settings.items():
        engine.SetRendererSetting(k, v)
    if os.environ.get("ROSTRUM_CAMSTATE"):
        f = UsdGeom.Camera(stage.GetPrimAtPath(cam)).GetCamera(Usd.TimeCode.Default()).frustum
        CameraUtil.ConformWindow(f, CameraUtil.MatchVertically, a.width / a.height)
        engine.SetCameraState(f.ComputeViewMatrix(), f.ComputeProjectionMatrix())
    else:
        engine.SetCameraPath(Sdf.Path(cam))
    engine.SetRenderBufferSize(Gf.Vec2i(a.width, a.height))
    engine.SetFraming(CameraUtil.Framing(Gf.Rect2i(Gf.Vec2i(0, 0), a.width, a.height)))
    engine.SetOverrideWindowPolicy(CameraUtil.MatchVertically)
    engine.SetRenderViewport(Gf.Vec4d(0, 0, a.width, a.height))
    params = UsdImagingGL.RenderParams()
    params.frame = Usd.TimeCode.Default()
    params.colorCorrectionMode = "sRGB"
    params.clearColor = Gf.Vec4f(0, 0, 0, 1)

    t0 = time.perf_counter()
    engine.Render(stage.GetPseudoRoot(), params)
    while not engine.IsConverged():
        if time.perf_counter() - t0 > a.timeout:
            sys.exit(f"{plugin} did not converge in {a.timeout} s")
        time.sleep(0.05)
        engine.Render(stage.GetPseudoRoot(), params)
    gl.glFinish()
    first = time.perf_counter() - t0
    times = []
    for _ in range(a.frames):  # steady-state frame time (camera unchanged, but every pass re-runs)
        t = time.perf_counter(); engine.Render(stage.GetPseudoRoot(), params); gl.glFinish()
        times.append((time.perf_counter() - t) * 1000)
    img = fbo.toImage()
    if os.environ.get("ROSTRUM_DEBUG"):
        from OpenGL import GL
        import numpy as np
        print("fbo", fbo.handle(), "bound draw fb", GL.glGetIntegerv(GL.GL_DRAW_FRAMEBUFFER_BINDING), "valid", fbo.isValid())
        arr = np.frombuffer(GL.glReadPixels(0, 0, a.width, a.height, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE), np.uint8)
        print("glReadPixels min/max/mean", arr.min(), arr.max(), arr.mean(), "qimage", img.format(), img.pixelColor(a.width // 2, a.height // 2).getRgb())
    if not mark.IsClean():
        for e in mark:
            print("USD error:", e.commentary, file=sys.stderr)
        sys.exit(f"{plugin}: USD/Hydra reported errors (above); {a.out} not written")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    if not img.save(a.out):
        sys.exit(f"could not write {a.out}")
    stats = dict(stage=a.stage, look=a.look, renderer=plugin, camera=cam, size=[a.width, a.height], gpu=gpu,
                 first_frame_s=round(first, 2), frame_ms=[round(t, 1) for t in times],
                 peak_ram_mb=peak_ram_mb(), settings={k: str(v) for k, v in settings.items()})
    with open(os.path.splitext(a.out)[0] + ".stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=1)
    print(json.dumps(stats))
    engine = None  # release Hydra before the GL context goes


if __name__ == "__main__":
    main()
