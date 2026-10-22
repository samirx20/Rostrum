"""The brush panel's side of the Draw tool: the kit's Inspector talks to this object as it does to a DocBridge (the
same `rows` / `setValue` / `toggleMore` surface), so the panel is built from the brush settings' own rules. The
brush is screen state (the next stroke), not the document: nothing here is an undo step. Painter (painter.py) is one.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_paint.marks import TIPS


class BrushPanel(QObject):
    """Needs `self.b` (the bridge), `self.brush` (brush.Brush) and `self.model` (the panel's RowsModel)."""
    brushChanged = Signal()

    @Property(QObject, constant=True)
    def rows(self):
        return self.model

    @Property("QVariantMap", notify=brushChanged)
    def brushNow(self):
        """The context bar's quick brush controls (ToolOptions.qml, Paint): the next stroke's values and the tips."""
        return {**self.brush.values, "tips": list(TIPS)}

    @Property("QVariantMap", notify=brushChanged)
    def selectedItem(self):
        return {"id": "brush", "label": self.brush.label(), "kind": "next stroke"}

    @Property(bool, notify=brushChanged)
    def moreOpen(self):
        return self.brush.more

    @Slot(str, "QVariant", result=bool)
    def setValue(self, param, value):
        return self.b.guard(lambda: self._brush_set(param, value))

    def _brush_set(self, param, value):
        self.brush.set(param, value)
        self.model.update(self.brush.rows())
        self.brushChanged.emit()

    @Slot(str)
    def beginScrub(self, param):
        pass                                        # the brush is not the document: nothing to gather into a step

    @Slot(str, "QVariant")
    def scrub(self, param, value):
        self.setValue(param, value)

    @Slot()
    def endScrub(self):
        pass

    @Slot()
    def toggleMore(self):
        self.brush.more = not self.brush.more
        self.model.update(self.brush.rows())
        self.brushChanged.emit()

    @Slot(str)
    def toggleAnimate(self, param):
        pass
