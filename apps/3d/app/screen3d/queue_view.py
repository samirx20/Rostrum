"""A finished render of the Render page's queue shown over the viewport: its last frame (qml/RenderView.qml reads
state, picture, path, note and calls dismiss, as it does for the Render button's job)."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot


class QueueView(QObject):
    """A finished render's last frame over the viewport (qml/RenderView.qml reads state, picture, path, note)."""
    changed = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self._row = {}

    state = Property(str, lambda self: "done" if self._row else "", notify=changed)
    picture = Property(str, lambda self: QUrl.fromLocalFile(self._row["picture"]).toString() if self._row.get("picture") else "", notify=changed)
    path = Property(str, lambda self: self._row.get("folder", ""), notify=changed)
    note = Property(str, lambda self: f'{self._row["shot"]} · {self._row["took"]}' if self._row else "", notify=changed)

    def put(self, row: dict):
        self._row = row
        self.changed.emit()

    @Slot()
    def dismiss(self):
        self.put({})
