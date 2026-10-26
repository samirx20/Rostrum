"""The brush panel's side of the Brush tool: the kit's Inspector talks to this object as it does to a DocBridge (the
same `rows` / `setValue` surface), so the settings panel is built from the brush settings' own rules (painting design
§2.1): the header "Painting · <layer> · <kind>", the quick rows, or every setting on "Edit brush ›" (`editing`, the
header then the brush's name). The presets (brush_presets.py) and My brushes (saved brushes, in the project and / or
the person's own library: rostrum2d/brushes.py; Save this brush, and on right-click the entries `myBrushes` gives each)
are what the brush flyout shows. The brush is screen state (the
next stroke), not the document: nothing here is an undo step. Painter (painter.py) is one.
"""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d import brushes
from rostrum2d.names import display_name
from rostrum_core.errors import RostrumError, codes
from rostrum_paint import library

from . import brush_presets, fill_aim
from .brush import LOADS, TOOL_PARTS


class BrushPanel(QObject):
    """Needs `self.b` (the bridge), `self.brush` (brush.Brush), `self.model` (the panel's RowsModel) and `self._aim()`
    (what the pen paints on) and `self.through()` (the element it paints through into its painted fill)."""
    brushChanged = Signal()
    toolChanged = Signal()
    headerChanged = Signal()        # what the pen paints on changed (the header): not the brush, so not brushChanged

    @Property(QObject, constant=True)
    def rows(self):
        return self.model

    @Property("QVariantMap", notify=brushChanged)
    def brushNow(self):
        """The next stroke's values, its preset and its name (the Brush row, [ and ], the brush ring)."""
        return {**self.brush.values, "preset": self.brush.preset, "name": self.brush.label()}

    def _tool(self) -> str:
        return self.b.paintTool.now

    @Property("QVariantMap", notify=toolChanged)
    def toolParts(self):
        """What the paint tool that is on shows (brush.TOOL_PARTS): `brush` (the brush's own row and Edit brush ›) and
        `gaps` (Close gaps). The quick rows follow the same table (brush.rows)."""
        return dict(TOOL_PARTS[self._tool()])

    @Slot()
    def toolSwitched(self):
        """A paint tool went on or off (paint_tool.py): the quick rows are that tool's, and a tool without a brush
        leaves Edit brush ›. Not `brushChanged`: the paint tool listens to that one."""
        tool = self._tool()
        if tool == getattr(self, "_switched", None):     # the paint tool says it changed for a part that isn't the tool
            return                                       # (one use() sends it up to five times): nothing to redo
        self._switched = tool
        if self.brush.editing and not TOOL_PARTS[tool]["brush"]:
            self.brush.editing = False
        self.model.update(self.brush.rows(bool(self.b.doc.folder), tool))
        self.toolChanged.emit()

    @Property("QVariantList", constant=True)
    def presets(self):
        return brush_presets.groups()

    @Property("QVariantList", notify=brushChanged)
    def myBrushes(self):
        """My brushes, by name: [{id, name, mark, markTip, menu}] (their strokes: image://brushes/<id>). `mark` only
        where needed: with a project open, a brush kept in just one of the two places says which; `menu` is its
        right-click entries, only those that apply (brush_menu)."""
        return [{"id": m["id"], "name": m["name"], **_mark(m["where"], bool(self.b.doc.folder)),
                 "menu": brush_menu(m["where"], bool(self.b.doc.folder))} for m in self._mine]

    @Slot()
    def refreshBrushes(self):
        """Read My brushes again (an agent may have saved one); the brush panel calls this as it opens."""
        self.b.guard(self._read_mine)

    def _read_mine(self):
        mine = brushes.saved(self.b.doc.folder)
        if mine == self._mine:
            return                  # nothing saved meanwhile: the panel opening redoes no binding (news only)
        self._mine = mine
        self.previews.keep({m["id"]: m["settings"] for m in self._mine})
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

    @Slot(str, str, result=bool)
    def brushAction(self, bid, act):
        """A My brushes right-click entry (brush_menu): duplicate, delete, keep:<place>, drop:<place>."""
        verb, _, place = act.partition(":")
        do = {"duplicate": lambda: brushes.duplicate(self.b.doc.folder, bid),
              "delete": lambda: brushes.remove(self.b.doc.folder, bid),
              "keep": lambda: brushes.keep(self.b.doc.folder, bid, place),
              "drop": lambda: brushes.drop(self.b.doc.folder, bid, place)}[verb]
        return self.b.guard(lambda: (do(), self._read_mine()))

    @Property("QVariantMap", notify=headerChanged)
    def selectedItem(self):
        if self.brush.editing:
            return {"id": "brush", "label": self.brush.label(), "kind": "brush", "subtitle": ""}   # its first group says "Brush"
        d, through = self._aim(), self.through()
        if self.b.opened.on:                # opened on its own: "Paper grain · 128 × 128 · used by 3 layers"
            return {"id": "brush", "label": "Painting", "kind": "brush", "kindLabel": self.b.opened.info.get("sub", "")}
        if through is not None:             # painting in place: "Paper grain · painted fill of card 2 · used by 3 layers"
            return {"id": "brush", "label": "Painting", "kind": "brush", "kindLabel": fill_aim.heading(self.b.doc, d, through)}
        name, kind = (display_name(d), self.b.kind_label(d)) if d else ("New drawing", "")
        said = kind == "" or re.fullmatch(rf"{re.escape(kind)}( \d+)?", name)     # the name already says it: "Drawing 2", not "Drawing 2 · Drawing"
        on = name if said else f"{name} · {kind}"
        return {"id": "brush", "label": "Painting", "kind": "brush", "kindLabel": on}

    editing = Property(bool, lambda self: self.brush.editing, notify=brushChanged)

    @Slot(bool)
    def setEditing(self, on):
        self.brush.editing = on
        self._rows_changed()

    @Slot(bool)
    def setTight(self, on):
        """A short window (Theme.tightFor): the pressure rows leave the quick rows (they stay on "Edit brush ›")."""
        if on != self.brush.tight:
            self.brush.tight = on
            self._rows_changed()

    @Slot(str)
    def setPreset(self, pid):
        mine = any(m["id"] == pid for m in self._mine)      # a library brush's tip / paper comes into the project first
        self.b.guard(lambda: (self.brush.apply_saved(brushes.use(self.b.doc.folder, pid)) if mine
                              else self.brush.apply_preset(pid), self._rows_changed()))

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
        self.model.update(self.brush.rows(bool(self.b.doc.folder), self._tool()))
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


PLACE = {"project": "this project", "library": "my library"}


def _mark(where: list, project_open: bool) -> dict:
    if not project_open or len(where) == 2:
        return {"mark": "", "markTip": ""}
    return {"mark": "project" if where == ["project"] else "library",
            "markTip": "Kept only in this project" if where == ["project"] else "Kept only in your library, not in this project"}


def brush_menu(where: list, project_open: bool) -> list[dict]:
    """A saved brush's right-click entries, only those that apply: Rename, Duplicate, Also keep in <the other place>,
    Remove from <a place> (while it is in both), Delete (everywhere)."""
    places = [p for p in PLACE if p == "library" or project_open]
    return ([{"value": "rename", "label": "Rename"}, {"value": "duplicate", "label": "Duplicate"}]
            + [{"value": f"keep:{p}", "label": f"Also keep in {PLACE[p]}"} for p in places if p not in where]
            + ([{"value": f"drop:{p}", "label": f"Remove from {PLACE[p]}"} for p in where] if len(where) == 2 else [])
            + [{"value": "delete", "label": "Delete"}])
