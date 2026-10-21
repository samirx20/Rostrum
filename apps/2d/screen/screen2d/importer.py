"""The Import panel's job: a file (SVG, PDF page, PSD, image, video) or a Figma frame into the open composition, through
rostrum2d.io.importing (the same code as the MCP tool run_import): one undo step, and the report of what didn't come across.

The slow part (importing.plan: read, download, parse) runs off the GUI thread (import_job.py), with a progress bar and Cancel;
the one change (importing.apply) is made back on the GUI thread, so the document is never changed from another thread.
Fails loudly: an error lands in the status line and the panel, nothing is half imported. A Figma token is passed straight
to the importer; it is never kept here, never printed, never put in a message.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QCoreApplication, QObject, QUrl, Signal, Slot
from rostrum2d.io import importing

from .import_job import Job

FITTED = ("svg", "pdf", "psd", "figma")          # the kinds whose page lands fitted in the composition (media is always)


class Importer(QObject):
    changed = Signal()
    _landed = Signal(object, str, bool)           # (plan, error line, cancelled): from the worker thread
    _progressed = Signal(float, str)

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b, self.job = bridge, Job()
        self._source, self._file, self._page, self._text, self._keep = "file", "", 1, "text", False
        self._state, self._note, self._progress, self._layers, self._report = "", "", 0.0, [], []
        self._landed.connect(self._finish)
        self._progressed.connect(self._on_progress)

    # ---- what QML shows (only what applies to the chosen source) ---------------------------------------------
    @Property(str, notify=changed)
    def source(self):
        return self._source

    @Property(str, notify=changed)
    def file(self):
        return self._file

    @Property(str, notify=changed)
    def fileName(self):
        return Path(self._file).name

    @Property(str, notify=changed)
    def kind(self):
        """"figma", or what the picked file is (svg | pdf | psd | image | video); "" until one is picked."""
        return "figma" if self._source == "figma" else self._kind()

    @Property(bool, notify=changed)
    def canKeepSize(self):
        """Whether "Keep original size" means anything here: only for a page that is fitted into the composition."""
        return self.kind in FITTED

    @Property(bool, notify=changed)
    def keepSize(self):
        return self._keep

    @Property(int, notify=changed)
    def page(self):
        return self._page

    @Property(str, notify=changed)
    def text(self):
        return self._text

    @Property(str, notify=changed)
    def state(self):
        """"" | "running" | "done" | "failed" | "cancelled"."""
        return self._state

    @Property(float, notify=changed)
    def progress(self):
        return self._progress

    @Property(str, notify=changed)
    def note(self):
        return self._note

    @Property("QVariantList", notify=changed)
    def report(self):
        """What didn't come across, one line each."""
        return list(self._report)

    @Property(bool, notify=changed)
    def ready(self):
        return self._source == "figma" or bool(self._file)

    def _kind(self) -> str:
        try:
            return importing.kind_of(self._file) if self._file else ""
        except ValueError:
            return ""

    # ---- what a person does ----------------------------------------------------------------------------------
    @Slot(str)
    def setSource(self, source):
        self._source = source
        self._clear()

    @Slot(str)
    def setFile(self, url):
        self._file = QUrl(url).toLocalFile() if url.startswith("file:") else url
        self._clear()

    @Slot(int)
    def setPage(self, page):
        self._page = max(1, int(page))
        self.changed.emit()

    @Slot(str)
    def setText(self, mode):
        self._text = mode
        self.changed.emit()

    @Slot(bool)
    def setKeepSize(self, keep):
        self._keep = bool(keep)
        self.changed.emit()

    @Slot()
    def run(self):
        self._go(dict(path=self._file, page=self._page, text=self._text))

    @Slot(str, str, str)
    def runFigma(self, key, frame, token):
        self._go(dict(figma={"key": key, "frame": frame, "token": token}))

    @Slot()
    def cancel(self):
        """Stop a running import at its next stage (import_job.py): nothing is put in."""
        if self.job.cancel():
            self._note = "Cancelling…"
            self.changed.emit()

    def running(self) -> bool:
        return self.job.running()

    def wait(self, timeout_s: float) -> bool:
        """For scripted steps: block until the job is over (True) or the time is up (False). Land the result on this thread."""
        self.job.wait(timeout_s)
        QCoreApplication.processEvents()
        return not self.running()

    def _go(self, kw):
        b = self.b
        if self.running():
            return b._fail("Error: import: one is already running; wait for it.")
        doc, comp_id, fit = b.doc, b.comp_id, not self._keep
        self._state, self._note, self._progress, self._layers, self._report = "running", "Starting…", 0.0, [], []
        self.changed.emit()
        b._set_status("Importing…")
        self.job.start(lambda progress, cancelled: importing.plan(doc, comp_id, fit=fit, progress=progress, cancelled=cancelled, **kw),
                       self._landed.emit, self._progressed.emit)

    def _on_progress(self, fraction, words):
        if self._state == "running" and not self.job.cancelled:
            self._progress, self._note = fraction, words + "…"
            self.changed.emit()

    def _finish(self, plan, line, stopped):
        """On the GUI thread: the one change (one undo step), or the cancel / error line. Nothing is half imported."""
        b = self.b
        if stopped or (plan and self.job.cancelled):
            self._state, self._note, self._progress = "cancelled", "Cancelled — nothing imported.", 0.0
            b._set_status("Import cancelled")
            return self.changed.emit()
        try:
            if plan is None:
                raise ValueError(line)
            r = importing.apply(b.doc, b.who, plan)
        except Exception as e:  # noqa: BLE001  whatever it was: say it, change nothing
            line = line or (e.line() if hasattr(e, "line") else f"Error: import: {e}")
            self._state, self._note, self._layers, self._report, self._progress = "failed", line, [], [], 0.0
            b._fail(line)
            return self.changed.emit()
        self._state, self._layers, self._report, self._progress = "done", r["layers"], r["report"], 1.0
        self._note = f'Imported {r["name"]}: {len(r["layers"])} layer{"" if len(r["layers"]) == 1 else "s"}'
        b._set_status(self._note + (f", {len(r['report'])} not carried over" if r["report"] else ""))
        if r["layers"]:
            b.select(r["layers"][-1])
        self.changed.emit()

    def _clear(self):
        if not self.running():
            self._state, self._note, self._progress, self._layers, self._report = "", "", 0.0, [], []
        self.changed.emit()
