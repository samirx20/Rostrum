"""The shot's simulation on the screen (brief 25, SPEC §10): QML's `backend.sim`. It feeds the Simulate row under the
timeline (SimRow.qml), the Scene panel's Simulation group (ScenePanel.qml), the render sheet's line (ExportSettings3D.qml)
and the right-click's ✓ on Simulate › (ContextMenu3D.qml).

The row is there only while the shot's scene has bodies. Its states: "not computed" (Simulate) → "running" (a bar
filling left to right with the frames computed; scrubbing works meanwhile) → "stored" (a solid bar, "Stored · 120
frames") → "out of date" (a striped bar, Simulate; the viewport keeps the old result) → "failed" (the core's line in red:
which body, which frame, what to do; until the next try).

Simulate runs as a job off the GUI thread: rostrum3d.sim.compute on a snapshot of the document, with its own engine
process (never the viewport's); when it lands, the GUI thread records it with the operation agents call too
(`sim.run {shot}`: one undo step; the result is already in the cache, so it only sets the shot's key). The state comes
from rostrum3d.sim.state, read again a moment after each change (one read per burst of edits, not per drag step).
"""
from __future__ import annotations

import copy
import threading

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from .sim_actions import KINDS, at_top, kind_of

RUNNING, FAILED = "running", "failed"
ROW_STATES = ("not computed", RUNNING, "stored", "out of date", FAILED)


def _sim():
    """Member B's rostrum3d.sim (state.state, compute.compute) as one namespace; None while it isn't there (the row stays absent)."""
    try:
        from rostrum3d.sim.compute import compute
        from rostrum3d.sim.state import state
    except ImportError:
        return None

    class Sim:
        pass
    Sim.state, Sim.compute = staticmethod(state), staticmethod(compute)
    return Sim


def _progress_of(*a, **k) -> tuple[int, int]:
    """(frames done, of) from compute's progress callback: the core's line {"progress": i, "of": n, "frame": f}, or (i, n)."""
    p = a[0] if a else k
    if isinstance(p, dict):
        return int(p.get("progress", p.get("done", 0))), int(p.get("of", p.get("total", 0)))
    if len(a) >= 2:
        return int(a[0]), int(a[1])
    return 0, 0


class SimJob(QObject):
    changed = Signal()
    _landed = Signal(str, str)              # (key, error line): from the worker thread
    _stepped = Signal(int, int)             # (frames done, of): from the worker thread

    def __init__(self, bridge, engine_factory=None, parent=None):
        super().__init__(parent or bridge)
        self._b, self._make_engine = bridge, engine_factory
        self._st: dict = {}
        self._running, self._failure, self._done, self._of = False, "", 0, 0
        self._kind, self._thread, self._demo = "", None, ""
        self._landed.connect(self._on_landed)
        self._stepped.connect(self._on_step)
        self._later = QTimer(self, singleShot=True, interval=150)     # one read per burst of edits
        self._later.timeout.connect(self.refresh)
        bridge.docChanged.connect(self._later.start)
        bridge.selectedItemsChanged.connect(self._on_selection)
        self.refresh()

    # ---- what QML reads -----------------------------------------------------------------------------------------
    @Property(bool, notify=changed)
    def shown(self):
        """The scene has bodies (Falls or Stays still): the row and the Scene panel's group are there."""
        return bool(self._st.get("bodies"))

    @Property(str, notify=changed)
    def state(self):
        """"not computed" | "running" | "stored" | "out of date" | "failed" ("" while the scene has no bodies)."""
        if not self.shown:
            return ""
        if self._running:
            return RUNNING
        if self._failure:
            return FAILED
        return self._st.get("state", "not computed")

    @Property(str, notify=changed)
    def label(self):
        """The row's words: "Not computed", "Simulating · frame 48 of 120", "Stored · 120 frames", "Out of date"."""
        s = self.state
        if s == RUNNING:
            return f"Simulating · frame {self._done} of {self._of}" if self._of else "Simulating…"
        if s == "stored":
            return f'Stored · {self._st.get("frames", 0)} frames'
        if s == FAILED:
            return self._failure
        return s[:1].upper() + s[1:]

    @Property(float, notify=changed)
    def filled(self):
        """How much of the bar is filled, 0..1: the frames computed while it runs; all of it once stored or out of date."""
        s = self.state
        if s == RUNNING:
            return self._done / self._of if self._of else 0.0
        return 1.0 if s in ("stored", "out of date") else 0.0

    @Property(bool, notify=changed)
    def canRun(self):
        """Simulate is offered (not while it runs, and not when the stored result is up to date)."""
        return self.state in ("not computed", "out of date", FAILED)

    @Property(str, notify=changed)
    def line(self):
        """The Scene panel's status line: "Drop 03: 12 bodies · stored · up to date"."""
        if not self.shown:
            return ""
        if self.state == RUNNING:
            return f'{self._shot_label()}: {self._bodies()} · simulating'
        if self.state == FAILED:
            return f'{self._shot_label()}: {self._bodies()} · failed'
        line = self._st.get("line") or f'{self._shot_label()}: {self._bodies()} · {self._st.get("state", "not computed")}'
        return line.removesuffix(" · Simulate")          # the button beside it says that

    @Property(str, notify=changed)
    def failure(self):
        return self._failure if self.state == FAILED else ""

    @Property(str, notify=changed)
    def renderLine(self):
        """The render sheet's line while the shot's result isn't up to date (the render computes it first)."""
        s = self.state
        if s in ("out of date", FAILED) and self._st.get("storedKey"):
            return f"{self._shot_label()}'s simulation is out of date — it will be computed first"
        if s in ("not computed", FAILED):
            return f"{self._shot_label()}'s simulation isn't computed yet — it will be computed first"
        return ""

    @Property(str, notify=changed)
    def kind(self):
        """The selection's one Simulate kind ("off" | "falls" | "still"; "" when mixed): the menu's ✓."""
        return self._kind

    @Property(bool, notify=changed)
    def ground(self):
        """The shot's Ground (simGround): a collider at height 0 (on unless turned off)."""
        shot = next((s for s in self._b.doc.data.get("shots", []) if s["id"] == self._b.shot_id), {})
        return bool(shot.get("simGround", True))

    @Slot(bool)
    def setGround(self, on):
        b = self._b
        b._guard(lambda: b._done(b.doc.apply([b.edit_call(b.shot_id, "simGround", bool(on))], b.who,
                                             label="Ground on" if on else "Ground off"), ""))

    def _shot_label(self) -> str:
        return self._b.shotInfo.get("label") or self._b.shot_id

    def _bodies(self) -> str:
        n = self._st.get("bodies", 0)
        return f"{n} bod{'y' if n == 1 else 'ies'}"

    # ---- reading the state ---------------------------------------------------------------------------------------
    @Slot()
    def refresh(self):
        if self._demo:
            return
        sim, b = _sim(), self._b
        try:
            st = sim.state(b.doc.data, b.shot_id, b.doc.folder) if sim else {}
        except Exception as e:  # noqa: BLE001  loudly: the row says why rather than vanishing
            st = {"bodies": self._st.get("bodies", 0) or 1, "state": "not computed"}
            self._failure = f"Error: simulate: {e}"
        self._st = st or {}
        if not self._st.get("bodies"):
            self._failure = ""                     # no bodies: nothing to say any more
        self._kind = kind_of(b.doc, list(b.selection))
        self.changed.emit()

    @Property(bool, notify=changed)
    def can(self):
        """The selection can be made a body (the rail's Simulate flyout is there): items of the scene's own list
        that a body can be (shapes, combines, imports, groups, clay, copies)."""
        doc, ids = self._b.doc, [i for i in self._b.selection if self._b.doc.has(i)]
        return bool(ids) and all(doc.item(i)["type"] in KINDS and at_top(doc, i) for i in ids)

    def _on_selection(self, *_):
        self._kind = kind_of(self._b.doc, list(self._b.selection))
        self.changed.emit()

    def commands(self) -> list[dict]:
        """Ctrl K: Simulate the shot, while the row offers it (the same job as its button)."""
        if not self.canRun:
            return []
        return [{"key": "sim:run", "label": f"Simulate {self._shot_label()}", "hint": self.line, "words": "simulation physics",
                 "do": self.simulate}]

    # ---- the job ---------------------------------------------------------------------------------------------
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @Slot()
    def simulate(self):
        """The row's (and the Scene panel's) Simulate: compute off the GUI thread, then record it (one undo step)."""
        sim, b = _sim(), self._b
        if sim is None or self.running() or not self.shown:
            return
        self._demo, self._failure, self._running, self._done = "", "", True, 0
        self._of = int(self._st.get("frames") or b.shot_info()["end"] - b.shot_info()["start"] + 1)
        self.changed.emit()
        data, shot, folder = copy.deepcopy(b.doc.data), b.shot_id, b.doc.folder     # edits made meanwhile are not in it
        kw = {"engine_factory": self._make_engine} if self._make_engine else {}
        b.say(f"Simulating {self._shot_label()}…")

        def work():
            try:
                key = sim.compute(data, shot, folder, progress=lambda *a, **k: self._stepped.emit(*_progress_of(*a, **k)), **kw)
                self._landed.emit(str(key or ""), "")
            except Exception as e:  # noqa: BLE001  the core's line (body, frame, fix) as it said it
                line = e.line() if hasattr(e, "line") else str(e)
                self._landed.emit("", line if line.startswith("Error") else f"Error: simulate: {line}")

        self._thread = threading.Thread(target=work, name="simulate", daemon=True)
        self._thread.start()

    def wait(self, timeout_s: float) -> bool:
        """For scripted steps: block until the job is over (True) or the time is up (False)."""
        if self._thread is not None:
            self._thread.join(timeout_s)
        return not self.running()

    def _on_step(self, done, of):
        self._done, self._of = done, of or self._of
        self.changed.emit()

    def _on_landed(self, key, error):
        self._running = False
        b = self._b
        if error:
            self._failure = error
            b.fail_line(error)
        else:
            ok = b._guard(lambda: b._done(b.doc.apply([{"op": "sim.run", "target": [b.shot_id], "args": {}}], b.who,
                                                      label=f"Simulate {self._shot_label()}"), ""))
            if ok:
                b.say(f"Simulated {self._shot_label()}: {self._st.get('frames') or self._of} frames stored")
        self.refresh()

    # ---- the layout check ------------------------------------------------------------------------------------
    def demo(self, state: str):
        """Fixed states for the layout check, never a simulation: one of ROW_STATES on a shot with twelve bodies."""
        if state not in ROW_STATES:
            raise ValueError(f"sim demo: {state!r} is not one of {', '.join(ROW_STATES)}")
        self._demo = state
        self._running, self._failure = state == RUNNING, ""
        self._done, self._of = (48, 120) if state == RUNNING else (0, 0)
        if state == FAILED:
            self._failure = ("Error: simulate: buds copy 7 starts inside bowl at frame 0: move it up 4 mm "
                             "or set Starts: Asleep until hit")
        shown = state if state not in (RUNNING, FAILED) else "out of date"
        label = self._shot_label()
        self._st = {"bodies": 13, "state": shown, "frames": 120, "storedKey": "demo" if shown != "not computed" else "",
                    "line": f"{label}: 13 bodies · {shown}" + (" · up to date" if shown == "stored" else "")}
        self.changed.emit()
