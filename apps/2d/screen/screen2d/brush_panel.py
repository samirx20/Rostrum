"""The brush panel's side of the Brush tool: the kit's Inspector talks to this object as it does to a DocBridge (the
same `rows` / `setValue` surface), so the settings panel is built from the brush settings' own rules (painting design
§2.1): the header "Painting · <layer> · <kind>", the quick rows, or every setting on "Edit brush ›" (`editing`, the
header then the brush's name). The presets (brush_presets.py) and My brushes (the project's saved brushes,
rostrum2d/brushes.py: Save this brush, Rename, Delete) are what the brush flyout shows. The brush is screen state (the
next stroke), not the document: nothing here is an undo step. Painter (painter.py) is one.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d import brushes
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

    @Property("QVariantList", notify=brushChanged)
    def myBrushes(self):
        """My brushes, by name: [{id, name}] (their strokes: image://brushes/<id>)."""
        return [{"id": m["id"], "name": m["name"]} for m in self._mine]

    canSave = Property(bool, lambda self: bool(self.b.doc.folder), notify=brushChanged)

    @Slot()
    def refreshBrushes(self):
        """Read My brushes again (an agent may have saved one); the brush panel calls this as it opens."""
        self.b.guard(self._read_mine)

    def _read_mine(self):
        self._mine = brushes.saved(self.b.doc.folder)
        self.previews.saved.update({m["id"]: m["settings"] for m in self._mine})
        if self.brush.preset in self.previews.saved:     # a renamed brush that is the brush: its new name
            self.brush.saved_name = next((m["name"] for m in self._mine if m["id"] == self.brush.preset), self.brush.saved_name)
        self.brushChanged.emit()

    @Slot(str, result=bool)
    def saveBrush(self, name):
        """Save this brush: the current settings (a loaded tip or paper by its project item) under `name`, in My
        brushes; it becomes the brush."""
        def save():
            self.brush.apply_saved(brushes.save(self.b.doc.folder, name, self.brush.values))
            self._read_mine()
            self._rows_changed()
        return self.b.guard(save)

    @Slot(str, str, result=bool)
    def renameBrush(self, bid, name):
        return self.b.guard(lambda: (brushes.rename(self.b.doc.folder, bid, name), self._read_mine()))

    @Slot(str, result=bool)
    def removeBrush(self, bid):
        return self.b.guard(lambda: (brushes.remove(self.b.doc.folder, bid), self._read_mine()))

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
        mine = next((m for m in self._mine if m["id"] == pid), None)
        self.b.guard(lambda: (self.brush.apply_saved(mine) if mine else self.brush.apply_preset(pid), self._rows_changed()))

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
