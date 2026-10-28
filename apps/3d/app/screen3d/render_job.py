"""The Render button (one click, F12): one Final-quality picture (Cycles) of the shot through its camera at the playhead frame, as a job off the
GUI thread with its own engine process (never the viewport's), through the same code as the MCP tool render_still
(rostrum3d.mcp.render.still): the same folder (the project's next render version, or the render cache), the same files
(png + exr, the EXR with the shot's passes as layers) and manifest. The engine process is ended when the job is over, so its GPU memory goes back.

A render reads a snapshot taken on press (scene, shot, history step), so edits made while it runs are not in it, and
its manifest says exactly which step it shows. Cancel ends that process by its own handle (never by name); the job then says "Render cancelled", shows no picture and
leaves nothing on disk (its half-made `.partial` folder is removed).
A failure is reported (red status, the error line), never as success.

Render always makes the Final picture (SPEC § 1 6:30): the Final preset whatever the shot's Quality says (a shot set to
Custom samples keeps its own, a shot set to Stylized renders Stylized: its look is not a Cycles one; other qualities
are the render sheet's, the ▾ beside the button). The moment it starts,
its note says how long it will take (render_guess: the kept measurement, else a first guess) and counts the seconds
against that. As soon as Cycles has drawn a little of the frame (its "step" lines: the share done), the time is measured
on this very frame instead (render_guess.left: "about 25 s left"), so a first guess that was far off is put right
within seconds. When it lands, the picture shows over the viewport (RenderView.qml) with Show in folder.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from rostrum_gui.export_sheet import ExportSheet

from rostrum3d.compile import describe, shot_info
from rostrum3d.engine import Engine
from rostrum3d.mcp.render import DocView, still
from rostrum3d.render_fields import engine_fields, passes, settings

from . import render_guess

FORMATS = ["png", "exr"]


def final_settings(shot: dict, info: dict) -> dict:
    """The Final look's Cycles settings (render_fields.settings): the shot's, at the Final preset unless it has Custom samples."""
    return settings(shot if shot.get("renderQuality") == "custom" else {**shot, "renderQuality": "final"}, info)


def button_settings(shot: dict, info: dict) -> dict:
    """The Render button's settings: Final (final_settings), or Stylized when the shot's Quality is Stylized."""
    return settings(shot, info) if shot.get("renderQuality") == "stylized" else final_settings(shot, info)


def cycles_of(data: dict, shot_id: str, info: dict) -> dict:
    """The Render button's Cycles settings ({samples, denoise}): the one place the Render button and the viewport's
    Final look take them from, so the converged view is the Render button's picture."""
    s = final_settings(next(x for x in data["shots"] if x["id"] == shot_id), info)
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
        self._expect, self._measured, self._t0, self._s = 0.0, False, 0.0, {}
        self._drawn = None                                 # [first, last] (share done, ms) Cycles reported for the frame
        self._tick = QTimer(self, interval=1000)          # the seconds so far, against the time it said
        self._tick.timeout.connect(self._on_tick)

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

    @Property(float, notify=changed)
    def progress(self):
        """0..1 while it runs: the seconds so far over the time it said (held under 1 until it lands)."""
        if self._state != "running" or self._expect <= 0:
            return 0.0
        return min(0.95, (time.monotonic() - self._t0) / self._expect)

    @Property(str, notify=changed)
    def clock(self):
        """The header's short form while it runs: "12 / 40 s" (seconds so far / the time it said)."""
        if self._state != "running":
            return ""
        so_far, said = time.monotonic() - self._t0, max(1.0, self._expect)
        return f"{so_far:.0f} / {said:.0f} s" if said < 90 else f"{so_far / 60:.0f} / {said / 60:.0f} min"

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @Slot()
    def showInFolder(self):
        """The finished picture, selected in Explorer (the kit's way, ExportSheet.showInFolder)."""
        ExportSheet.showInFolder(self)

    def _running_note(self) -> str:
        so_far = time.monotonic() - self._t0
        if (left := render_guess.left(*self._drawn) if self._drawn else None) is not None:
            self._expect, self._measured = so_far + left, True     # measured on this frame: the time left
            return f"Rendering the final picture · {render_guess.words_left(left)}" + (f" · {so_far:.0f} s so far" if so_far >= 1 else "")
        said = render_guess.words(self._expect, self._measured)
        late = so_far > self._expect * 1.15 + 2
        return (f"Rendering the final picture · {said}" + (f" · {so_far:.0f} s so far" if so_far >= 1 else "")
                + (" (taking longer than that)" if late else ""))

    def _on_tick(self):
        if self._state == "running" and self._note != "Cancelling…":
            self._note = self._running_note()
            self.changed.emit()

    @Slot()
    def start(self):
        if self.running() or self._bridge.queue.running():
            return self._bridge.fail_line("Error: render: one is already running; wait for it.")
        b = self._bridge
        try:
            info, scene = shot_info(b.doc.data, b.shot_id), describe(b.doc.data, b.shot_id, b.doc.folder)
        except ValueError as e:
            return self._finish("", 0.0, f"Error: render: {e}")
        frame, self._at = b.frame, b.frame
        self._stop = stop = threading.Event()
        snap = DocView.of(b.doc)                      # what the manifest records: the same view the render_still tool takes
        shot = next(x for x in b.doc.data["shots"] if x["id"] == b.shot_id)
        s = button_settings(shot, info)                # Final (or Stylized), the shot's size and EXR passes, as render_still reads them
        layers = passes(shot) if s["renderer"] == "cycles" else []
        size, folder, cyc = (s["width"], s["height"]), b.doc.folder, engine_fields(s)
        self._expect, self._measured = render_guess.guess(scene, s, getattr(self._make_engine, "exe", None))
        self._t0, self._s, self._drawn = time.monotonic(), s, None
        self._state = "running"
        self._note = self._running_note()
        self._tick.start()
        self.changed.emit()
        look = "Stylized" if s["renderer"] == "stylized" else "Final"
        b.say(f"Rendering frame {frame} at {look}, {render_guess.words(self._expect, self._measured)}")

        def work():
            t0, engine = time.monotonic(), None
            try:
                engine = self._engine = self._make_engine()
                if stop.is_set():
                    raise RuntimeError(CANCELLED)
                _, files, _ = still("render", snap, info, scene, engine, frame, s["renderer"], size, FORMATS, 0, cyc, folder, layers, stop.is_set,
                                    step=self._on_step)
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

    def _on_step(self, line: dict):
        """Cycles' share of the frame so far (worker thread): keep the first report and the newest."""
        now = (line["fraction"], line["ms"])
        self._drawn = [self._drawn[0] if self._drawn else now, now]

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

    def demo(self, state: str, picture: str = ""):
        """Fixed states for the layout check, never a render: "running" (12 s into a 40 s guess, the clock stopped) or "done"."""
        self._tick.stop()
        if state == "running":
            self._expect, self._measured, self._t0 = 40.0, False, time.monotonic() - 12
            self._state, self._picture = "running", ""
            self._note = self._running_note()
        else:
            self._state, self._picture, self._note = "done", picture, "Rendered in 38.2 s"
        self.changed.emit()

    def wait(self, timeout_s: float) -> bool:
        """For scripted steps: block until the job is over (True) or the time is up (False)."""
        if self._thread is not None:
            self._thread.join(timeout_s)
        return not self.running()

    def _on_landed(self, png, secs, error):
        self._finish(png, secs, error)

    def _finish(self, png, secs, error):
        self._tick.stop()
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
            if self._s:
                render_guess.learn(self._s, secs)
            self._bridge.say(f"Rendered frame {self._at} in {secs:.1f} s")
        self.changed.emit()
