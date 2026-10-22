"""The Export button: any export format of the open composition as a job off the GUI thread, through the same code as the MCP
tool render_export (rostrum2d.mcp.exporting.run): the same formats, the same files, the same manifest.

The formats, and the settings each one takes, come from that code's data (io/formats.py FORMATS + Lottie); a setting that
doesn't apply is not in `settings` (export_rows.py). A press snapshots the scene: edits made while it runs are not in the
file. A failure is reported (red status, the error line), never as success; Cancel stops the job (export_job.py).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Property, QCoreApplication, QObject, QUrl, Signal, Slot
from rostrum2d.mcp import export_name, exporting
from rostrum_core.mcp.files import RENDER_DIR

from . import export_rows
from .export_job import Job


class Exporter(QObject):
    changed = Signal()
    _landed = Signal("QVariantMap", str)          # (facts, error line): from the worker thread
    _progressed = Signal(float)
    taken = Signal(str, bool)                     # (the name of a file already there, whether it can be replaced): QML asks

    def __init__(self, bridge, engine_factory=None, parent=None):
        super().__init__(parent or bridge)
        self._bridge, self.job = bridge, Job(engine_factory)
        self._state, self._note, self._progress, self._facts = "", "", 0.0, {}
        self._fmt, self._values = "mp4", {}
        self._target = ""                        # a path the person chose ("" = the project's renders folder)
        self._asked: tuple | None = None         # the press that is waiting for Replace / Keep both / Cancel
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
        """The chosen format's defaults: transparency on where it can be carried, its first bit depth, its default quality, the
        whole composition."""
        r = self._row()
        self._values = {"alpha": r["alpha"], "depth": r["depths"][0] if r["depths"] else None, "quality": r["quality"],
                        "start": 0.0, "end": self._duration()}

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
    def fileName(self):
        """What the file will be called: the chosen path's name, else the project's and the composition's, in words."""
        return self._chosen().name if self._target else self._stem() + ("" if self._row()["sequence"] else self._row()["ext"])

    @Property(str, notify=changed)
    def target(self):
        """The path the person chose to save to ("" = the project's renders folder)."""
        return self._target

    @Property(str, notify=changed)
    def destination(self):
        """The folder the file goes into, in words: shown before the export starts, while it runs and after."""
        if self._target:
            return str(self._chosen().parent)
        folder = self._bridge.doc.folder
        if folder and self._fmt not in exporting.DATA:
            return f"{Path(folder) / 'renders' / self._bridge.doc.item_id} (in a new version folder)"
        return f"{RENDER_DIR} (the render cache)"

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

    def _stem(self) -> str:
        return export_name.stem_of(self._bridge.doc, self._comp_id)

    def _chosen(self) -> Path:
        """The chosen path, ending in the format's extension (a sequence: the folder it is written into)."""
        p, ext = Path(self._target), self._row()["ext"]
        return p if self._row()["sequence"] or p.suffix.lower() == ext else p.with_suffix(ext)

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
        kind = {"depth": int, "alpha": bool, "quality": str}.get(key, float)
        self._values[key] = kind(value)
        if key == "start":
            self._values["end"] = max(self._values["end"], self._values["start"] + 1 / self._comp()["fps"])
        self.changed.emit()

    @Slot(str)
    def setTarget(self, path):
        """A path from the Save dialog (a file:// url or a path); "" goes back to the renders folder."""
        if self.running():
            return
        self._target = QUrl(path).toLocalFile() if path.startswith("file:") else path
        self.changed.emit()

    @Slot()
    def request(self):
        """The Export button: when the chosen file is already there, ask first (the `taken` signal); else start."""
        if self.running() or not self._target:
            return self.start()
        where = self._chosen()
        if where.exists():
            self._asked = (where,)
            return self.taken.emit(where.name, not self._row()["sequence"])
        self.start()

    @Slot(str)
    def answer(self, choice):
        """Replace | both (keep both: " 2" is added) | anything else cancels."""
        asked, self._asked = self._asked, None
        if not asked or choice not in ("replace", "both"):
            return
        if choice == "both":
            self._target = str(export_name.free_path(asked[0]))
            self.changed.emit()
        self._go(overwrite=choice == "replace")

    @Slot()
    def showInFolder(self):
        """The file selected in the file manager (a sequence: its folder opened)."""
        f = (self._facts.get("files") or [""])[0]
        if not f:
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", f"/select,{f}"] if not self._row()["sequence"] else ["explorer", str(Path(f).parent)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", f])
        else:
            subprocess.Popen(["xdg-open", str(Path(f).parent)])

    @Slot()
    def start(self):
        self._go()

    def _go(self, overwrite=False):
        b = self._bridge
        if self.running():
            return b._fail("Error: export: one is already running; wait for it.")
        self._facts, self._progress = {}, 0.0
        try:
            v = self._values
            s = exporting.settings("export", self._fmt, self._duration(), v["alpha"], v["depth"], v["start"], v["end"], v["quality"])
            scene = exporting.snapshot(b.doc, self._comp_id, self._fmt)   # the snapshot: edits made while it runs are not in the file
        except Exception as e:  # noqa: BLE001
            return self._finish({}, e.line() if hasattr(e, "line") else f"Error: export: {e}")
        fmt, doc = self._fmt, b.doc
        item, folder, seq = doc.item_id, doc.folder, doc.seq
        name, out = self._stem(), (self._chosen() if self._target else None)
        self._state, self._note = "running", f"Exporting {self._row()['label']}…"
        self.changed.emit()
        b._set_status(self._note)

        def export(make_engine):
            return exporting.run("export", scene, fmt, s, folder, item, seq, out,
                                 lambda done, total: self._progressed.emit(done / total if total else 0.0), make_engine,
                                 name=name, overwrite=overwrite)
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
            self._bridge._set_status(f"Exported {Path(self.path).name}")
        self.changed.emit()
