"""The Import panel's job: a file (SVG, PDF page, PSD, image, video) or a Figma frame into the open composition, through
rostrum2d.io.importing.run (the same code as the MCP tool run_import): one undo step, and the report of what didn't come across.

Fails loudly: an error lands in the status line and the panel, nothing is half imported. A Figma token is passed straight
to the importer; it is never kept here, never printed, never put in a message.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from rostrum2d.io import importing


class Importer(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b = bridge
        self._source, self._file, self._page, self._text = "file", "", 1, "text"
        self._state, self._note, self._layers, self._report = "", "", [], []

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

    @Property(int, notify=changed)
    def page(self):
        return self._page

    @Property(str, notify=changed)
    def text(self):
        return self._text

    @Property(str, notify=changed)
    def state(self):
        """"" | "done" | "failed"."""
        return self._state

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

    @Slot()
    def run(self):
        self._go(lambda: importing.run(self.b.doc, self.b.who, self.b.comp_id, self._file, None, self._page, self._text))

    @Slot(str, str, str)
    def runFigma(self, key, frame, token):
        self._go(lambda: importing.run(self.b.doc, self.b.who, self.b.comp_id, figma={"key": key, "frame": frame, "token": token}))

    def _go(self, work):
        try:
            r = work()
        except Exception as e:  # noqa: BLE001  whatever it was: say it, change nothing
            line = e.line() if hasattr(e, "line") else f"Error: import: {e}"
            self._state, self._note, self._layers, self._report = "failed", line, [], []
            self.b._fail(line)
        else:
            self._state, self._layers, self._report = "done", r["layers"], r["report"]
            self._note = f'Imported {r["name"]}: {len(r["layers"])} layer{"" if len(r["layers"]) == 1 else "s"}'
            self.b._set_status(self._note + (f", {len(r['report'])} not carried over" if r["report"] else ""))
            if r["layers"]:
                self.b.select(r["layers"][-1])
        self.changed.emit()

    def _clear(self):
        self._state, self._note, self._layers, self._report = "", "", [], []
        self.changed.emit()
