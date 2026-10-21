"""The Render button: one final picture (Cycles) of the shot through its camera at the playhead frame, as a job off the
GUI thread with its own engine process (never the viewport's), through the same code as the MCP tool render_still
(rostrum3d.mcp.render.still): the same folder (the project's next render version, or the render cache), the same files
(png + exr) and manifest. The engine process is ended when the job is over, so its GPU memory goes back.

A render reads a snapshot taken on press (scene, shot, history step), so edits made while it runs are not in it, and
its manifest says exactly which step it shows. A failure is reported (red status, the error line), never as success.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from rostrum3d.compile import describe, shot_info
from rostrum3d.engine import Engine
from rostrum3d.mcp.render import still

SETTINGS = {"samples": 128, "denoise": True}     # render_still's defaults
FORMATS = ["png", "exr"]


class RenderJob(QObject):
    changed = Signal()
    _landed = Signal(str, float, str)             # (png path, seconds, error line): from the worker thread

    def __init__(self, bridge, engine_factory=None, parent=None):
        super().__init__(parent or bridge)
        self._bridge, self._make_engine, self._at = bridge, engine_factory or Engine, 0
        self._state, self._picture, self._note, self._thread = "", "", "", None
        self._landed.connect(self._on_landed)

    @Property(str, notify=changed)
    def state(self):
        """"" (nothing shown) | "running" | "done" | "failed"."""
        return self._state

    @Property(str, notify=changed)
    def picture(self):
        return QUrl.fromLocalFile(self._picture).toString() if self._picture else ""

    @Property(str, notify=changed)
    def path(self):
        return self._picture

    @Property(str, notify=changed)
    def note(self):
        return self._note

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @Slot()
    def start(self):
        if self.running():
            return self._bridge.fail_line("Error: render: one is already running; wait for it.")
        b = self._bridge
        try:
            info, scene = shot_info(b.doc.data, b.shot_id), describe(b.doc.data, b.shot_id)
        except ValueError as e:
            return self._finish("", 0.0, f"Error: render: {e}")
        frame = self._at = b.frame
        snap = SimpleNamespace(item_id=b.doc.item_id, seq=b.doc.seq)     # what the manifest records
        size, folder = (info["width"], info["height"]), b.doc.folder
        self._state, self._note = "running", f"Rendering frame {frame} with Cycles…"
        self.changed.emit()
        b.say(self._note)

        def work():
            t0, engine = time.monotonic(), None
            try:
                engine = self._make_engine()
                _, files, _ = still("render", snap, info, scene, engine, frame, "cycles", size, FORMATS, 0, SETTINGS, folder)
                png = next(str(f) for f in files if f.suffix == ".png")
                self._landed.emit(png, time.monotonic() - t0, "")
            except Exception as e:  # noqa: BLE001  fail loudly, whatever it was
                line = e.line() if hasattr(e, "line") else f"Error: render: {type(e).__name__}: {e}"
                self._landed.emit("", time.monotonic() - t0, line)
            finally:
                if engine is not None:
                    engine.close()

        self._thread = threading.Thread(target=work, name="render-still", daemon=True)
        self._thread.start()

    @Slot()
    def dismiss(self):
        if not self.running():
            self._state, self._picture, self._note = "", "", ""
            self.changed.emit()

    def wait(self, timeout_s: float) -> bool:
        """For scripted steps: block until the job is over (True) or the time is up (False)."""
        if self._thread is not None:
            self._thread.join(timeout_s)
        return not self.running()

    def _on_landed(self, png, secs, error):
        self._finish(png, secs, error)

    def _finish(self, png, secs, error):
        if error or not png or not Path(png).is_file():
            self._state, self._picture = "failed", ""
            self._note = error or f"Error: render: the picture {png or '(none)'} was not written"
            self._bridge.fail_line(self._note)
        else:
            self._state, self._picture = "done", png
            self._note = f"Rendered in {secs:.1f} s"
            self._bridge.say(f"Rendered frame {self._at} in {secs:.1f} s")
        self.changed.emit()
