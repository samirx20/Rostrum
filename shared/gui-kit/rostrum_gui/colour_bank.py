"""The colours every colour picker offers (kit ColorPicker.qml reads it as the context property `colourBank`): the
project's colours, the brand kit's, and the eyedropper's screen pick. The app fills it and connects `added` to its own
operation (2D: swatch.add), so saving a colour is a change in the document like any other.

    bank = colour_bank.bank()          # the process's one bank; app.py sets it as `colourBank` on every window
    bank.set_project(["#ff7a45", …]); bank.set_brand("Northwind", ["#111827", …])
    bank.added.connect(lambda hex_: doc.apply([{"op": "swatch.add", "args": {"color": hex_}}], who))
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QPoint, Signal, Slot
from PySide6.QtGui import QGuiApplication


class ColourBank(QObject):
    changed = Signal()
    added = Signal(str)                 # the picker's "+": the app saves it (and refills `project`)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project, self._brand, self._brand_name = [], [], ""

    def set_project(self, colours):
        if list(colours) != self._project:
            self._project = list(colours)
            self.changed.emit()

    def set_brand(self, name: str, colours):
        if (name, list(colours)) != (self._brand_name, self._brand):
            self._brand_name, self._brand = name, list(colours)
            self.changed.emit()

    project = Property("QVariantList", lambda self: self._project, notify=changed)
    brand = Property("QVariantList", lambda self: self._brand, notify=changed)
    brandName = Property(str, lambda self: self._brand_name, notify=changed)

    @Slot(str)
    def add(self, hex_: str):
        self.added.emit(hex_.lower())

    @Slot(int, int, result=str)
    def pixel(self, x: int, y: int) -> str:
        """The colour on screen at (x, y) in global coordinates: anything showing there, the canvas, a picture,
        another program. "" when no screen holds the point (the picker then keeps its colour)."""
        screen = QGuiApplication.screenAt(QPoint(x, y))
        if screen is None:
            return ""
        geo, ratio = screen.geometry(), screen.devicePixelRatio()
        shot = screen.grabWindow(0, x - geo.x(), y - geo.y(), 1, 1).toImage()
        if shot.isNull():
            return ""
        c = shot.pixelColor(0, 0) if shot.width() == 1 else shot.pixelColor(int(ratio) // 2, int(ratio) // 2)
        return c.name()


_BANK: ColourBank | None = None


def bank() -> ColourBank:
    global _BANK
    if _BANK is None:
        _BANK = ColourBank()
    return _BANK
