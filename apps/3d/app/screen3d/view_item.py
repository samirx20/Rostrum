"""The live view drawn inside the window (the Rostrum3DView QML item, apps/3d/core/view/viewport_item.h): the engine's
own core runs in this process on Qt Quick's render thread and draws straight into the viewport, so a dab or an orbit
reaches the screen without a second program, a pipe or a picture copy (proofs/3d-viewport: 92 -> 8 ms a dab).

`ItemEngine` has the engine client's method names (rostrum3d.engine.Engine), so the viewport's worker jobs (picks,
clay strokes, placing) are unchanged: the same scene JSON and the same requests (ENGINE_CONTRACT.md) go to the item.
What the window doesn't draw itself stays with the engine program, which loads the same scene when first asked:
the Final look (progressive Cycles, a picture), a mesh's geometry and unfolding, saving, inspecting.

`in_window()` says whether this window can: a real (not offscreen) window on OpenGL with the module built. Pictures
for checks (--shot, the layout check) are drawn offscreen, where there is no OpenGL, so they keep the picture path.
"""
from __future__ import annotations

import ctypes
import hashlib
import itertools
import json
import os
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Qt, Signal, Slot

from rostrum3d import runtime

MODULE = runtime.REPO / "apps" / "3d" / "core" / ".build" / "install" / "qml"   # the Rostrum3DView module (build.bat)
ANSWER_S = 120.0             # a request the window doesn't answer in this long fails loudly (a scene of many clays)


_ON = [False]                # prepare() ran: this app's windows draw the live view themselves


def on() -> bool:
    return _ON[0]


def module_dir() -> Path:
    return Path(os.environ["ROSTRUM3D_QML"]) if os.environ.get("ROSTRUM3D_QML") else MODULE


def wanted() -> bool:
    """Before the app starts: draw the live view in the window (ROSTRUM3D_VIEW=picture keeps the engine's pictures)."""
    return (sys.platform == "win32" and os.environ.get("ROSTRUM3D_VIEW", "window") != "picture"
            and os.environ.get("QT_QPA_PLATFORM", "") != "offscreen"
            and (module_dir() / "Rostrum3DView" / "qmldir").is_file())


def prepare():
    """Before the app's first window: OpenGL for Qt Quick (the item draws with GL), the fast graphics chip, and the 3D
    libraries findable in this process (DLL folders on PATH, Hydra's plug-ins). Returns the QML import folder."""
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
    prefer_fast_gpu()
    env = runtime.runtime_env()
    for k in ("PATH", "PXR_PLUGINPATH_NAME", "CYCLES_DEVICE"):
        os.environ[k] = env[k]
    _ON[0] = True
    return module_dir()


def prefer_fast_gpu():
    """Ask Windows to run this program's graphics on the fast chip. An engine program exports NvOptimusEnablement, but
    Python can't, and on this laptop Qt's GL context landed on the AMD chip inside the processor. Windows' own per-program
    choice (Settings > Display > Graphics, the same registry value) does it, also for OpenGL, when set before the first
    context. It is set for this Python program only and says so on the console the first time."""
    if sys.platform != "win32":
        return
    import winreg
    buf = ctypes.create_unicode_buffer(1024)
    ctypes.windll.kernel32.GetModuleFileNameW(None, buf, len(buf))
    exe = buf.value
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\DirectX\UserGpuPreferences") as k:
        try:
            have = winreg.QueryValueEx(k, exe)[0]
        except OSError:
            have = ""
        if "GpuPreference=2;" in have:
            return
        parts = [p for p in have.split(";") if p and not p.startswith("GpuPreference=")]
        winreg.SetValueEx(k, exe, 0, winreg.REG_SZ, ";".join(["GpuPreference=2", *parts]) + ";")
        print(f"rostrum3d: Windows asked to run {exe} on the fast graphics chip (Settings > Display > Graphics)",
              file=sys.stderr)


class ViewLink(QObject):
    """The Rostrum3DView item as Python sees it, on the GUI thread. `ask` (any thread but the GUI's) sends one request
    and waits for its reply; `show` hands over the newest picture's view request, answered by `drawn`."""
    drawn = Signal(dict)             # a picture's reply (the engine's `view` reply, plus "frame", "tRender0/1")
    shown = Signal(int, float)       # frame on screen, its swap's time (ms, time.perf_counter's clock)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.item = None
        self._there = threading.Event()          # the item exists (LiveView.qml attached it)
        self._ids = itertools.count(1)
        self._waiting: dict[int, list] = {}
        self._lock = threading.Lock()
        self.gl = ""

    @Slot(QObject)
    def attach(self, item):
        self.item = item
        self._there.set()

    def _wait_item(self):
        if not self._there.wait(ANSWER_S):
            raise RuntimeError("the window's view never appeared (LiveView.qml)")

    def ask(self, req: dict, timeout_s: float = ANSWER_S) -> dict:
        if threading.current_thread() is threading.main_thread():
            raise RuntimeError("the window's view answers on the screen's thread: ask from a worker")
        self._wait_item()
        name, n, box = next(iter(req)), next(self._ids), [threading.Event(), None]
        with self._lock:
            self._waiting[n] = box
        t0 = time.perf_counter()
        QMetaObject.invokeMethod(self.item, "post", Qt.ConnectionType.DirectConnection, Q_ARG(int, n),
                                 Q_ARG(str, json.dumps(req)))
        if not box[0].wait(timeout_s):
            with self._lock:
                self._waiting.pop(n, None)
            raise RuntimeError(f"the window's view did not answer {name} in {timeout_s:g} s")
        out = box[1]
        if not out.get("ok"):
            raise RuntimeError(f"3D view refused {name}: {out.get('error', 'no reason given')}")
        out["ms"] = (time.perf_counter() - t0) * 1000
        return out

    def show(self, req: dict):
        """From the worker (never the GUI thread before the item exists: it waits for it)."""
        self._wait_item()
        QMetaObject.invokeMethod(self.item, "show", Qt.ConnectionType.DirectConnection, Q_ARG(str, json.dumps({"view": req})))

    # --- from the item (LiveView.qml), on the GUI thread
    @Slot(int, str)
    def answered(self, n, reply):
        with self._lock:
            box = self._waiting.pop(n, None)
        if box is not None:
            box[1] = json.loads(reply)
            box[0].set()

    @Slot(str)
    def onDrawn(self, reply):
        self.drawn.emit(json.loads(reply))

    @Slot(int, float)
    def onShown(self, frame, t_ms):
        self.shown.emit(frame, t_ms)


class ItemEngine:
    """The engine client's methods over the window's view, the engine program behind it for the rest (module doc)."""

    def __init__(self, link: ViewLink, engine):
        self.link, self.engine = link, engine
        self._hash, self._scene = None, None
        self.pid = os.getpid()                   # the process doing the live view's work (checks count its cycles)

    def ensure_scene(self, scene: dict) -> bool:
        h = hashlib.sha256(json.dumps(scene, sort_keys=True).encode()).hexdigest()
        self._scene = scene
        if h == self._hash:
            return False
        self.link.ask({"scene": scene})
        self._hash = h
        return True

    def pick(self, **req) -> dict:
        return self.link.ask({"pick": req})

    def sculpt(self, **req) -> dict:
        return self.link.ask({"sculpt": req})

    def sculpt_view(self, view: dict, **req) -> tuple[dict, None]:
        """A stroke event and the picture after it, drawn in the same frame; the picture is on screen, not returned."""
        out = self.link.ask({"sculpt": {**req, "view": view}})
        v = out.pop("view", None)
        if v is not None:
            out["pictured"] = True
            self.link.drawn.emit({**v, "frame": out.get("frame")})
        return out, None

    def clay_info(self, item: str) -> dict:
        return self.link.ask({"clay_info": {"item": item}})

    def show(self, req: dict):
        self.link.show(req)

    # --- the engine program's
    def _engine(self):
        if self._scene is not None:
            self.engine.ensure_scene(self._scene)
        return self.engine

    def view(self, **req):
        return self._engine().view(**req)

    def geometry(self, item: str) -> dict:
        return self._engine().geometry(item)

    def unfold(self, item: str, size: int = 2048) -> dict:
        return self._engine().unfold(item, size)

    def take_notices(self) -> list[str]:
        return self.engine.take_notices()

    def release(self):
        self.engine.release()

    def close(self):
        self.engine.close()
