"""The Export button: any export format of the open composition as a job off the GUI thread, through the same code as the MCP
tool render_export (rostrum2d.mcp.exporting.run): the same formats, the same files, the same manifest.

The formats, and the settings each one takes, come from that code's data (io/formats.py FORMATS + Lottie); a setting that
doesn't apply is not in `settings` (export_rows.py). A press snapshots the scene: edits made while it runs are not in the
file. A failure is reported (red status, the error line), never as success; Cancel stops the job (export_job.py).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QCoreApplication, QObject, QUrl, Signal, Slot
from rostrum2d.mcp import exporting, render

from . import export_rows
from .export_job import Job


class Exporter(QObject):
    changed = Signal()
    _landed = Signal("QVariantMap", str)          # (facts, error line): from the worker thread
    _progressed = Signal(float)

    def __init__(self, bridge, engine_factory=None, parent=None):
        super().__init__(parent or bridge)
        self._bridge, self.job = bridge, Job(engine_factory)
        self._state, self._note, self._progress, self._facts = "", "", 0.0, {}
        self._fmt, self._values = "mp4", {}
        self._comp_id = bridge.comp_id          # the comp shown, until another is picked
        self._reset()
        self._landed.connect(self._finish)
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
        """The rows for the chosen format, only the ones that apply (export_rows.py)."""
        return export_rows.settings(self._row(), self._values, self._duration())

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
        """The result's file (a sequence: its folder)."""
        f = self._facts.get("files") or []
        return str(Path(f[0]).parent) if self._row()["sequence"] and f else (f[0] if f else "")

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
        return export_rows.facts(self._row(), self._facts, self.path) if self._state == "done" and self._facts else []

    def running(self) -> bool:
        return self.job.running()

    # ---- what a person does -------------------------------------------------------------------------------
    @Slot(str)
    def setFormat(self, name):
        self._choose(name, self._comp_id)

    @Slot(str)
    def setComp(self, comp_id):
        if self._bridge.doc.has(comp_id):
            self._choose(self._fmt, comp_id)

    def _choose(self, fmt, comp_id):
        """A new format or composition: its default settings, the last result cleared."""
        if self.running() or (fmt, comp_id) == (self._fmt, self._comp_id):
            return
        self._fmt, self._comp_id = fmt, comp_id
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
        self._facts, self._progress = {}, 0.0
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

        def export(make_engine):
            return exporting.run("export", scene, fmt, s, folder, item, seq, None,
                                 lambda done, total: self._progressed.emit(done / total if total else 0.0), make_engine)
        self.job.start(export, self._landed.emit)

    @Slot()
    def cancel(self):
        """Stop a running export (export_job.py): no file is left, the panel says Cancelled."""
        if self.job.cancel():
            self._note = "Cancelling…"
            self.changed.emit()

    @Slot()
    def dismiss(self):
        if not self.running():
            self._state, self._note, self._facts, self._progress = "", "", {}, 0.0
            self.changed.emit()

    def wait(self, timeout_s: float) -> bool:
        """For scripted steps: block until the job is over (True) or the time is up (False). Land the result on this thread."""
        self.job.wait(timeout_s)
        QCoreApplication.processEvents()
        return not self.running()

    def _on_progress(self, p):
        if self._state == "running":
            self._progress = p
            self.changed.emit()

    def _finish(self, facts, error):
        if self.job.cancelled and not facts.get("files") and not error:
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
