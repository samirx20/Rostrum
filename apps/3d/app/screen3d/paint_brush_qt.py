"""Paint mode's Brush group, for QML as `paintMode.brush` (SPEC §5, mockup 06): the kit's bar settings
(rostrum_paint.fields.BAR: tip, size, colour, opacity) as the kit's own rows, so InspectorRow draws them exactly as it
draws any field (it talks to this object as its `bridge`). The brush is screen state, never in the document: each
stroke stores every setting it was painted with (the kit's stroke.add), so changing the brush changes the next stroke.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core import RostrumError
from rostrum_gui import rows
from rostrum_gui.model import RowsModel

from . import paint_mode as P

_OP = SimpleNamespace(params=P.BAR_PARAMS)


class PaintBrush(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = P.start_brush()
        self.model = RowsModel(rows.ROLES, self)
        self._static = rows.layout(_OP)
        self.model.reset(self._rows())

    def _rows(self):
        return rows.evaluate(self._static, self.values, {}, False)

    def _set(self, name, value):
        p = next((q for q in P.BAR_PARAMS if q.name == name), None)
        if p is None:
            return False
        try:
            self.values[name] = p.check(round(value, 4) if isinstance(value, float) else value, f"brush.{name}")
        except RostrumError as e:                 # a value out of range: said on the row, the brush unchanged
            print(e.line())
            return False
        self.model.update(self._rows())
        self.changed.emit()
        return True

    rows = Property(QObject, lambda s: s.model, constant=True)
    size = Property(float, lambda s: float(s.values["size"]), notify=changed)
    colour = Property(str, lambda s: s.values["color"], notify=changed)

    # --- InspectorRow's bridge
    @Slot(str, "QVariant", result=bool)
    def setValue(self, name, value):
        return self._set(name, value)

    @Slot(str)
    def beginScrub(self, name):
        pass

    @Slot(str, "QVariant")
    def scrub(self, name, value):
        self._set(name, value)

    @Slot()
    def endScrub(self):
        pass

    @Slot()
    def cancelScrub(self):
        pass

    @Slot(str)
    def toggleGroup(self, group):
        pass

    @Slot(str)
    def toggleAnimate(self, name):
        pass
