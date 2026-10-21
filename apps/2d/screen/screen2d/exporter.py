"""The Export button: any export format of the open composition as a job off the GUI thread, through the same code as the MCP
tool render_export (rostrum2d.mcp.exporting.run): the same formats, the same files, the same manifest.

The formats, and the settings each one takes, come from that code's data (io/formats.py FORMATS + Lottie); a setting that
doesn't apply to the chosen format is not in `settings` at all. A press takes a snapshot of the scene, so edits made while
it runs are not in the file. A failure is reported (red status, the error line), never as success.
"""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from rostrum2d.mcp import exporting, render


class Exporter(QObject):
    changed = Signal()
    _landed = Signal("QVariantMap", str)          # (facts, error line): from the worker thread
    _progressed = Signal(float)

    def __init__(self, bridge, engine_factory=None, parent=None):
        super().__init__(parent or bridge)
        self._bridge, self._engine_factory = bridge, engine_factory
        self._state, self._note, self._progress, self._facts, self._thread = "", "", 0.0, {}, None
        self._fmt, self._values = "mp4", {}
        self._comp_id, self._engine, self._cancelled = bridge.comp_id, None, False    # the comp shown, until another is picked
        self._reset()
        self._landed.connect(self._on_landed)
        self._progressed.connect(self._on_progress)

    def _row(self) -> dict:
        return exporting.info("export", self._fmt)

    def _comp(self) -> dict:
        return self._bridge.doc.item(self._comp_id)

    def _duration(self) -> float:
        return float(self._comp().get("duration", 5.0))

    def _reset(self):
        """The chosen format's defaults: transparency on where it can be carried, its first bit depth, the whole composition."""
        r = self._row()
        self._values = {"alpha": r["alpha"], "depth": r["depths"][0] if r["depths"] else None, "start": 0.0, "end": self._duration()}

    # ---- what QML shows -----------------------------------------------------------------------------------
    @Property("QVariantList", constant=True)
    def formats(self):
        return [{"value": r["name"], "label": r["label"]} for r in exporting.formats()]

    @Property("QVariantList", notify=changed)
    def comps(self):
        """The document's compositions to choose from; empty when there is only one (nothing to choose)."""
        rows = self._bridge.doc.data.get("comps", [])
        return [{"value": c["id"], "label": c.get("name") or c["id"]} for c in rows] if len(rows) > 1 else []

    @Property(str, notify=changed)
    def comp(self):
        """The composition that will be exported (the one on screen until another is picked)."""
        return self._comp_id

    @Property(str, notify=changed)
    def format(self):
        return self._fmt

    @Property("QVariantList", notify=changed)
    def settings(self):
        """The rows for the chosen format, only the ones that apply: {key, kind toggle|choice|number, label, value, …}."""
        r, v = self._row(), self._values
        rows = []
        if r["alpha"]:
            rows.append({"key": "alpha", "kind": "toggle", "label": "Transparency", "value": v["alpha"]})
        if len(r["depths"]) > 1:
            rows.append({"key": "depth", "kind": "choice", "label": "Bit depth", "value": str(v["depth"]),
                         "options": [{"value": str(d), "label": f"{d}-bit"} for d in r["depths"]]})
        if r["range"]:
            d = self._duration()
            rows.append({"key": "start", "kind": "number", "label": "From", "value": v["start"], "from": 0.0, "to": d, "unit": "s"})
            rows.append({"key": "end", "kind": "number", "label": "To", "value": v["end"], "from": 0.0, "to": d, "unit": "s"})
        return rows

    @Property(str, notify=changed)
    def state(self):
        """"" (nothing started) | "running" | "done" | "failed" | "cancelled"."""
        return self._state

    @Property(float, notify=changed)
    def progress(self):
        return self._progress

    @Property(str, notify=changed)
    def note(self):
        return self._note

    @Property(str, notify=changed)
    def path(self):
        """The result's file (a png sequence: its folder)."""
        f = self._facts.get("files") or []
        return str(Path(f[0]).parent) if self._fmt == "png" and f else (f[0] if f else "")

    @Property("QVariantList", notify=changed)
    def facts(self):
        """The result in words, read back from the file: [{label, text}]."""
        return self._facts_rows()

    @Property(str, notify=changed)
    def picture(self):
        """A picture of the result, where the file is one (png, gif: the first frame)."""
        f = self._facts.get("files") or []
        pic = next((p for p in f if p.lower().endswith((".png", ".gif"))), "")
        return QUrl.fromLocalFile(pic).toString() if pic and self._state == "done" else ""

    @Property("QVariantList", notify=changed)
    def report(self):
        """Lottie: what it couldn't carry, one line each."""
        return list(self._facts.get("report") or [])

    def _facts_rows(self):
        f = self._facts
        if self._state != "done" or not f:
            return []
        rows = [{"label": "File", "text": self.path}, {"label": "Frames", "text": f'{f["frames"]} at {f["fps"]:g} fps'}]
        c = f.get("checked") or {}
        if c.get("size"):
            rows.append({"label": "Size", "text": "×".join(str(n) for n in c["size"])})
        if self._row()["alpha"]:
            rows.append({"label": "Transparency", "text": "kept" if f["alpha"] else "not kept"})
        if len(self._row()["depths"]) > 1:
            rows.append({"label": "Bit depth", "text": f'{f["depth"]}-bit'})
        return rows

    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ---- what a person does -------------------------------------------------------------------------------
    @Slot(str)
    def setFormat(self, name):
        if self.running() or name == self._fmt:
            return
        self._fmt = name
        self._reset()
        self._state, self._note, self._facts = "", "", {}
        self.changed.emit()

    @Slot(str)
    def setComp(self, comp_id):
        if self.running() or comp_id == self._comp_id or not self._bridge.doc.has(comp_id):
            return
        self._comp_id = comp_id
        self._reset()
        self._state, self._note, self._facts = "", "", {}
        self.changed.emit()

    @Slot(str, "QVariant")
    def setSetting(self, key, value):
        if self.running() or key not in self._values:
            return
        self._values[key] = int(value) if key == "depth" else bool(value) if key == "alpha" else float(value)
        if key == "start":
            self._values["end"] = max(self._values["end"], self._values["start"] + 1 / self._comp()["fps"])
        self.changed.emit()

    @Slot()
    def start(self):
        b = self._bridge
        if self.running():
            return b._fail("Error: export: one is already running; wait for it.")
        self._facts, self._progress, self._cancelled = {}, 0.0, False
        try:
            v = self._values
            s = exporting.settings("export", self._fmt, self._duration(), v["alpha"], v["depth"], v["start"], v["end"])
            scene = render.scene_of(b.doc, self._comp_id)        # the snapshot: edits made while it runs are not in the file
        except Exception as e:  # noqa: BLE001
            return self._finish({}, e.line() if hasattr(e, "line") else f"Error: export: {e}")
        fmt, doc = self._fmt, b.doc
        item, folder, seq = doc.item_id, doc.folder, doc.seq
        self._state, self._note = "running", f"Exporting {self._row()['label']}…"
        self.changed.emit()
        b._set_status(self._note)

        def make_engine():                      # remembered, so Cancel can stop it
            self._engine = (self._engine_factory or exporting._engine)()
            return self._engine

        def work():
            try:
                facts = exporting.run("export", scene, fmt, s, folder, item, seq, None,
                                      lambda done, total: self._progressed.emit(done / total if total else 0.0), make_engine)
                self._landed.emit(facts, "")
            except Exception as e:  # noqa: BLE001  fail loudly, whatever it was (a cancel is the one expected stop)
                self._landed.emit({}, "" if self._cancelled else e.line() if hasattr(e, "line") else f"Error: export: {type(e).__name__}: {e}")

        self._thread = threading.Thread(target=work, name="export", daemon=True)
        self._thread.start()

    @Slot()
    def cancel(self):
        """Stop a running export: the engine is stopped by its own handle, the unfinished files are removed by run()."""
        eng = self._engine
        if not self.running() or eng is None or self._cancelled:
            return
        self._cancelled = True
        self._note = "Cancelling…"
        self.changed.emit()
        if eng.proc.poll() is None:
            eng.proc.kill()

    @Slot()
    def dismiss(self):
        if not self.running():
            self._state, self._note, self._facts, self._progress = "", "", {}, 0.0
            self.changed.emit()

    def wait(self, timeout_s: float) -> bool:
        """For scripted steps: block until the job is over (True) or the time is up (False). Land the result on this thread."""
        if self._thread is not None:
            self._thread.join(timeout_s)
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.processEvents()
        return not self.running()

    def _on_progress(self, p):
        if self._state == "running":
            self._progress = p
            self.changed.emit()

    def _on_landed(self, facts, error):
        self._finish(facts, error)

    def _finish(self, facts, error):
        if self._cancelled and not facts.get("files") and not error:
            self._state, self._facts, self._note, self._progress = "cancelled", {}, "Cancelled", 0.0
            self._bridge._set_status("Export cancelled")
        elif error or not facts.get("files"):
            self._state, self._facts, self._note = "failed", {}, error or "Error: export: nothing was written"
            self._bridge._fail(self._note)
        else:
            self._state, self._facts, self._progress = "done", dict(facts), 1.0
            self._note = f'Exported {facts["frames"]} frames'
            self._bridge._set_status(f"{self._note}: {self.path}")
        self.changed.emit()
