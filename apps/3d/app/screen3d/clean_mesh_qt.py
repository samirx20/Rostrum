"""Make a clean mesh in the Clay panel (PR4; rostrum3d/remesh.py, ops_clay_clean.py), for QML as `viewport.clay.cleanObj`.

The panel's last group while a clay is selected: Faces (about how many four-sided faces; screen state, 4000 to start)
and **Make clean mesh**. A click reads the clay's surface from the window's engine (a moment), then rebuilds it off the
window's thread in its own process: the row turns into a bar with "Rebuilding · 3 s" and **Cancel** (ends that process
by its own handle). When it lands, `clay.clean_mesh` adds the mesh beside the clay and hides the clay, one undo step,
and the new mesh is selected; it finds the rebuild in the cache, so nothing is computed twice. A failure is one plain
red line under the button until the next try. Agents call `clay.clean_mesh` themselves (it waits for the rebuild).
"""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from rostrum3d import remesh
from rostrum3d.ops_clay_clean import DEFAULT_FACES


class CleanMesh(QObject):
    changed = Signal()
    _said = Signal(str)                      # a progress line, from the worker thread
    _landed = Signal(str, str)               # (clay id, error line), from the worker thread

    def __init__(self, tool):
        super().__init__(tool)
        self.t, self.b = tool, tool.b
        self._faces, self._line, self._failure = DEFAULT_FACES, "", ""
        self.read_ms = 0.0
        self._thread, self._stop, self._proc, self._t0 = None, threading.Event(), None, 0.0
        self._said.connect(self._on_said)
        self._landed.connect(self._on_landed)
        self._tick = QTimer(self, interval=250)          # the seconds go on while the library works
        self._tick.timeout.connect(self.changed)
        tool.changed.connect(self._on_tool)

    def _clay(self):
        return self.t._item()

    # ---- what QML reads ------------------------------------------------------------------------------------------
    shown = Property(bool, lambda s: s._clay() is not None, notify=changed)
    running = Property(bool, lambda s: s.busy(), notify=changed)
    faces = Property(int, lambda s: s._faces, notify=changed)
    failure = Property(str, lambda s: s._failure, notify=changed)
    lo = Property(int, lambda s: remesh.FACES[0], constant=True)
    hi = Property(int, lambda s: remesh.FACES[1], constant=True)

    @Property(str, notify=changed)
    def label(self):
        """The bar's words while it runs: what it does now and for how long."""
        if not self.busy():
            return ""
        return f"{self._line} · {time.monotonic() - self._t0:.0f} s" if self._line else "Reading the clay…"

    def busy(self) -> bool:
        return self._thread is not None

    # ---- what QML calls ------------------------------------------------------------------------------------------
    @Slot(float)
    def setFaces(self, n):
        n = int(min(max(round(n), remesh.FACES[0]), remesh.FACES[1]))
        if n != self._faces:
            self._faces = n
            self.changed.emit()

    @Slot()
    def make(self):
        clay = self._clay()
        if clay is None or self.busy():
            return
        self._failure, self._line, self._t0 = "", "", time.monotonic()
        self._stop.clear()
        self._thread = True                              # running at once: the bar shows before the engine answers
        self._tick.start()
        self.changed.emit()
        QTimer.singleShot(0, lambda: self._start(clay["id"]))

    @Slot()
    def cancel(self):
        if self.busy():
            self._stop.set()
            self._line = "Cancelling"
            self.changed.emit()

    def wait(self, timeout_s: float) -> bool:
        """For scripted steps: block until the job is over (True) or the time is up (False)."""
        if isinstance(self._thread, threading.Thread):
            self._thread.join(timeout_s)
        return not isinstance(self._thread, threading.Thread) or not self._thread.is_alive()

    def demo(self, state: str):
        """Fixed looks for the layout check, never a rebuild: "running" (the bar at 3 s) or "failed" (its red line)."""
        if state not in ("running", "failed"):
            raise ValueError(f"clean demo: {state!r} is not running or failed")
        self._thread = "demo" if state == "running" else None
        self._line, self._t0 = "Rebuilding", time.monotonic() - 3
        self._failure = ("" if state == "running" else
                         "Couldn't make a clean mesh: the clay's surface has fewer than 4 triangles; sculpt something first")
        self.changed.emit()

    # ---- the job -------------------------------------------------------------------------------------------------
    def _start(self, clay_id):
        if self._stop.is_set():
            return self._landed.emit(clay_id, "")
        try:
            t0 = time.perf_counter()
            raw = remesh.surface(self.b.doc.data, clay_id)          # the window's engine, on its own thread
            self.read_ms = (time.perf_counter() - t0) * 1000         # for checks: how long the window waited
        except Exception as e:  # noqa: BLE001  the engine's own words
            return self._on_landed(clay_id, f"could not read the clay: {e}")
        faces = self._faces

        def work():
            try:
                remesh.compute(raw, faces, remesh.key_of(raw, faces), progress=self._said.emit,
                               stopped=self._stop.is_set, started=self._started)
                self._landed.emit(clay_id, "")
            except remesh.Cancelled:
                self._landed.emit(clay_id, "")
            except Exception as e:  # noqa: BLE001  the rebuild's own words
                self._landed.emit(clay_id, str(e))

        self._thread = threading.Thread(target=work, name="clean-mesh", daemon=True)
        self._thread.start()

    def _started(self, proc):
        self._proc = proc

    def _on_said(self, line):
        self._line = "Rebuilding" if line.startswith("rebuilding the surface") else line[:1].upper() + line[1:]
        self.changed.emit()

    def _on_landed(self, clay_id, error):
        self._thread, self._proc = None, None
        self._tick.stop()
        cancelled = self._stop.is_set()
        if error:
            self._failure = f"Couldn't make a clean mesh: {error}"
            self.b.fail_line(f"Error: clean mesh: {error}")
        elif cancelled:
            self.b.say("Clean mesh cancelled")
        else:
            self._record(clay_id)
        self.changed.emit()

    def _record(self, clay_id):
        """clay.clean_mesh (it finds the rebuild in the cache), one undo step; the new mesh selected."""
        b = self.b
        before = {i["id"] for i in _all(b.doc.data.get("items", []))}
        call = [{"op": "clay.clean_mesh", "target": [clay_id], "args": {"faces": self._faces}}]
        if not b._guard(lambda: b._apply(call, "Make a clean mesh")):
            return
        new = next((i for i in _all(b.doc.data.get("items", [])) if i["id"] not in before and i["type"] == "mesh"), None)
        if new is not None:
            b.select(new["id"])
            b.say(f'Clean mesh "{new.get("name")}": {len(new.get("faceCounts", [])):,} faces; the clay is hidden')

    def _on_tool(self):
        self.changed.emit()


def _all(items):
    for i in items:
        yield i
        yield from _all(i.get("children", []))
