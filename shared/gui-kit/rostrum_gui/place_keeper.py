"""Reopen at the same place, the Qt side (rostrum_core.places keeps the data; INTERACTION.md 1.19). One per
ProjectFiles. Screen state: nothing here is a change or an undo step.

    keeper.note()              the place may have changed (selection, playhead, scene, view): saved a moment later
    keeper.save(doc, bridge)   saved now (leaving a project, quitting)
    keeper.restore(doc, bridge) put back after the project is shown; what no longer exists (a deleted scene or layer)
                               is dropped quietly, one item at a time, and the rest restores

The app gives AppFiles `place(bridge) -> dict` and `restore_place(bridge, dict)`; without them nothing happens.
A failure to remember or restore a place is printed, never stops the app: it only means starting at the top.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QTimer

from rostrum_core import places

DELAY_MS = 600


class PlaceKeeper(QObject):
    def __init__(self, kind, current, parent=None):
        """`current() -> (doc, bridge)` is what is on screen now."""
        super().__init__(parent)
        self.kind, self._current = kind, current
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DELAY_MS)
        self._timer.timeout.connect(lambda: self.save(*self._current()))

    @property
    def on(self) -> bool:
        return bool(self.kind.place and self.kind.restore_place)

    def note(self) -> None:
        if self.on:
            self._timer.start()

    def save(self, doc, bridge, folder=None) -> None:
        """`folder`: keep it under that folder instead (a renamed project's place follows it)."""
        self._timer.stop()
        if not self.on or doc is None or bridge is None or not doc.folder or not doc.item_id:
            return
        try:
            places.save(self.kind.app, folder or doc.folder, doc.item_id, self.kind.place(bridge))
        except Exception as e:  # noqa: BLE001  a place not kept only means starting at the top next time
            print(f"place not kept: {e}", file=sys.stderr)

    def restore(self, doc, bridge) -> None:
        if not self.on or bridge is None or not doc.folder or not doc.item_id:
            return
        place = places.keep_existing(places.load(self.kind.app, doc.folder, doc.item_id), doc.has)
        if not place:
            return
        try:
            self.kind.restore_place(bridge, place)
        except Exception as e:  # noqa: BLE001
            print(f"place not restored: {e}", file=sys.stderr)
