"""The Render button: one final picture (Cycles) of the shot through its camera at the playhead frame, as a job off the
GUI thread with its own engine process (never the viewport's), through the same code as the MCP tool render_still
(rostrum3d.mcp.render.still): the same folder (the project's next render version, or the render cache), the same files
(png + exr) and manifest. The engine process is ended when the job is over, so its GPU memory goes back.

A render reads a snapshot taken on press (scene, shot, history step), so edits made while it runs are not in it, and
its manifest says exactly which step it shows. Cancel ends that process by its own handle (never by name); the job then says "Render cancelled", shows no picture and
leaves no finished render (the half-made folder stays `.partial`, which render_still never lists as a version).
A failure is reported (red status, the error line), never as success.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from rostrum3d.compile import describe, shot_info
from rostrum3d.engine import Engine
from rostrum3d.mcp.render import DocView, still
from rostrum3d.render_fields import settings

FORMATS = ["png", "exr"]


def cycles_of(data: dict, shot_id: str, info: dict) -> dict:
    """The shot's Cycles settings ({samples, denoise}) as agents read them (render_fields.settings): the one place the
    Render button, Export and the viewport's Final look take them from."""
    s = settings(next(x for x in data["shots"] if x["id"] == shot_id), info)
    return {"samples": s["samples"], "denoise": s["denoise"]}
CANCELLED = "Render cancelled"


class RenderJob(QObject):
    changed = Signal()
    _landed = Signal(str, float, str)             # (png path, seconds, error line): from the worker thread

    def __init__(self, bridge, engine_factory=None, parent=None):
        super().__init__(parent or bridge)
        self._bridge, self._make_engine, self._at = bridge, engine_factory or Engine, 0
        self._state, self._picture, self._note, self._thread = "", "", "", None
        self._engine, self._stop = None, threading.Event()
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
        frame, self._at = b.frame, b.frame
        self._stop = stop = threading.Event()
        snap = DocView.of(b.doc)                      # what the manifest records: the same view the render_still tool takes
        s = settings(next(x for x in b.doc.data["shots"] if x["id"] == b.shot_id), info)   # the shot's render settings, as agents read them
        size, folder, cyc = (s["width"], s["height"]), b.doc.folder, {"samples": s["samples"], "denoise": s["denoise"]}
        self._state, self._note = "running", f"Rendering frame {frame} with Cycles…"
        self.changed.emit()
        b.say(self._note)

        def work():
            t0, engine = time.monotonic(), None
            try:
                engine = self._engine = self._make_engine()
                if stop.is_set():
                    raise RuntimeError(CANCELLED)
                _, files, _ = still("render", snap, info, scene, engine, frame, "cycles", size, FORMATS, 0, cyc, folder)
                png = next(str(f) for f in files if f.suffix == ".png")
                self._landed.emit(png, time.monotonic() - t0, "")
            except Exception as e:  # noqa: BLE001  fail loudly, whatever it was
                if stop.is_set():                       # the engine was ended on purpose: that is not a failure
                    return self._landed.emit("", time.monotonic() - t0, CANCELLED)
                line = e.line() if hasattr(e, "line") else f"Error: render: {type(e).__name__}: {e}"
                self._landed.emit("", time.monotonic() - t0, line)
            finally:
                self._engine = None
                if engine is not None:
                    engine.close()

        self._thread = threading.Thread(target=work, name="render-still", daemon=True)
        self._thread.start()

    @Slot()
    def cancel(self):
        """Stop the running render: end its engine process (our own child, by handle). The worker then lands as cancelled."""
        if not self.running():
            return
        self._stop.set()
        engine = self._engine
        if engine is not None and engine.proc is not None and engine.proc.poll() is None:
            engine.proc.kill()                          # by the Popen handle; the reply loop sees the process end
        self._note = "Cancelling…"
        self.changed.emit()

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
        if error == CANCELLED:                      # back to idle; never a picture, never red
            self._state, self._picture, self._note = "", "", CANCELLED
            self._bridge.say(CANCELLED)
            return self.changed.emit()
        if error or not png or not Path(png).is_file():
            self._state, self._picture = "failed", ""
            self._note = error or f"Error: render: the picture {png or '(none)'} was not written"
            self._bridge.fail_line(self._note)
        else:
            self._state, self._picture = "done", png
            self._note = f"Rendered in {secs:.1f} s"
            self._bridge.say(f"Rendered frame {self._at} in {secs:.1f} s")
        self.changed.emit()
