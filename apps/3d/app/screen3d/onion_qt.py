"""Onion skin in the viewport, for QML as `viewport.onion` (SPEC §9, Animate rail › Onion skin, O): on or off and
which frames (at the previous and next keys, or 2 and 4 frames each way). Screen state only: the document and its
history never see it. The viewport asks `request()` for the view request's `ghosts` (rostrum3d/onion.py decides
them; the core draws them, ENGINE_CONTRACT.md § 4); the Final look draws none (the core refuses ghosts there).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from rostrum3d import onion


class Onion(QObject):
    changed = Signal()

    def __init__(self, viewport):
        super().__init__(viewport)
        self.v, self.b = viewport, viewport.bridge
        self._on, self._mode = False, "keys"

    on = Property(bool, lambda s: s._on, notify=changed)
    mode = Property(str, lambda s: s._mode, notify=changed)
    # [{value, label}] for the flyout's choice, the order shown
    modes = Property("QVariantList", lambda s: [{"value": "keys", "label": "At the keys"},
                                                {"value": "frames", "label": "2 and 4 frames"}], constant=True)

    @Slot(bool)
    def setOn(self, on):
        if bool(on) != self._on:
            self._on = bool(on)
            self.changed.emit()
            self.v.redraw()

    @Slot()
    def toggle(self):
        self.setOn(not self._on)

    @Slot(str)
    def setMode(self, mode):
        if mode not in onion.MODES:
            return self.b.fail_line(f"Error: onion skin: {mode!r} is not one of {', '.join(onion.MODES)}.")
        if mode != self._mode:
            self._mode = mode
            self.changed.emit()
            if self._on:
                self.v.redraw()

    def request(self, drawn: set[str]) -> dict:
        """{"ghosts": [...]} for the quick look's view request, or {} (off, nothing selected, nothing to show)."""
        sel = self.b.selected
        if not self._on or sel not in drawn or not self.b.doc.has(sel):
            return {}
        found = onion.ghosts(self.b.doc.item(sel), self.b.frame, self.b.shot_info(), self._mode)
        return {"ghosts": found} if found else {}
