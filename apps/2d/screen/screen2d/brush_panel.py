"""The brush panel's side of the Brush tool: the kit's Inspector talks to this object as it does to a DocBridge (the
same `rows` / `setValue` surface), so the settings panel is built from the brush settings' own rules (painting design
§2.1): the header "Painting · <layer> · <kind>", the quick rows, or every setting on "Edit brush ›" (`editing`, the
header then the brush's name). The presets (brush_presets.py) are what the brush flyout shows. The brush is screen
state (the next stroke), not the document: nothing here is an undo step. Painter (painter.py) is one.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d.names import display_name
from rostrum_core.errors import RostrumError, codes
from rostrum_paint import library

from . import brush_presets
from .brush import LOADS


class BrushPanel(QObject):
    """Needs `self.b` (the bridge), `self.brush` (brush.Brush), `self.model` (the panel's RowsModel) and `self._aim()`
    (what the pen paints on)."""
    brushChanged = Signal()

    @Property(QObject, constant=True)
    def rows(self):
        return self.model

    @Property("QVariantMap", notify=brushChanged)
    def brushNow(self):
        """The next stroke's values, its preset and its name (the Brush row, [ and ], the brush ring)."""
        return {**self.brush.values, "preset": self.brush.preset, "name": self.brush.label()}

    @Property("QVariantList", constant=True)
    def presets(self):
        return brush_presets.groups()

    @Property("QVariantMap", notify=brushChanged)
    def selectedItem(self):
        if self.brush.editing:
            return {"id": "brush", "label": self.brush.label(), "kind": "brush", "kindLabel": "Brush"}
        d = self._aim()
        name, kind = (display_name(d), self.b.kind_label(d)) if d else ("New drawing", "")
        on = name if kind in ("", name) else f"{name} · {kind}"     # "Drawing", not "Drawing · Drawing"
        return {"id": "brush", "label": "Painting", "kind": "brush", "kindLabel": on}

    editing = Property(bool, lambda self: self.brush.editing, notify=brushChanged)

    @Slot(bool)
    def setEditing(self, on):
        self.brush.editing = on
        self._rows_changed()

    @Slot(str)
    def setPreset(self, pid):
        self.b.guard(lambda: (self.brush.apply_preset(pid), self._rows_changed()))

    @Slot(str, "QVariant", result=bool)
    def setValue(self, param, value):
        return self.b.guard(lambda: self._brush_set(param, value))

    @Slot(str, str, result=bool)
    def loadChoice(self, param, path):
        """Load picture… on Tip picture or Paper: the file is kept in the project (library.load) and becomes the
        brush's choice; the lists grow by themselves (library.generation)."""
        def load():
            if not self.b.doc.folder:
                raise RostrumError(codes.BAD_ARGUMENT, "picture.load", path, "this document isn't saved in a project yet, "
                                   "so there is no project to keep the picture in", hint="Save it first.")
            self._brush_set(param, library.load(self.b.doc.folder, path, LOADS[param], Path(path).stem)["id"])
        return self.b.guard(load)

    def _brush_set(self, param, value):
        self.brush.set(param, value)
        self._rows_changed()

    def _rows_changed(self):
        self.model.update(self.brush.rows(bool(self.b.doc.folder)))
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

    @Slot(str)
    def toggleAnimate(self, param):
        pass
