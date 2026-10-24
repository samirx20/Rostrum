"""The settings panel's screen state (a slot mix-in for DocBridge, see parts.py): which groups are open, the search
text, and jumping to one field. Opt-in: a bridge with `sections = True` lays its rows out by importance
(sections.py: essentials, every other group folded to its name, search); every other bridge keeps the More row.
None of this is a document change. Open and folded groups are remembered by name across selections (Timing opened
on one layer is open on the next). The mix-in uses the bridge's `_kit` (op_kind, static, open_groups, search), `model`,
`_refresh`, `_set_status`, `searchChanged` and `fieldRevealed`.
"""
from __future__ import annotations

from PySide6.QtCore import Slot

from . import rows, sections
from .parts import SlotMixin


class SectionSlots(SlotMixin):
    sections = False                        # True: essentials + folded groups + search (else the More row)

    def _layout(self) -> list[dict]:
        """The static rows for the selected item's kind, as this bridge lays them out right now."""
        op, kind = self._kit.op_kind
        if not self.sections:
            return rows.layout(op, kind)
        return (sections.search_layout if self._kit.search.strip() else sections.layout)(op, kind)

    @Slot(str)
    def toggleGroup(self, group):
        """Fold or open a group (from its heading or its name in the row of names); the choice outlives the selection.
        A group a switch turns on (rows.py `switch`) is added or removed instead: its switch set to its `on` / `off`
        value (a toggle True / False, motion blur 180° / Off), one change."""
        row = next((r for r in self.model.rows if r.get("fold") == group), None)
        if row and row.get("own"):          # the kind's own group is always open
            return
        if row and row.get("switch"):
            return self.setValue(row["switch"], row["off"] if row["open"] else row["on"])
        self._kit.open_groups[group] = not (row and row["open"])
        self._refresh()

    @Slot(str)
    def setSearch(self, text):
        if text == self._kit.search:
            return
        relayout = bool(text.strip()) != bool(self._kit.search.strip())
        self._kit.search = text
        if relayout:                        # searching <-> not: another layout (the model swaps the list)
            self._kit.static = self._layout()
        self._refresh()
        self.searchChanged.emit()

    @Slot(str, result=bool)
    def revealField(self, name):
        """Bring one field into view: open its group (or More), clear a search that hides it, then QML scrolls to
        the row, puts the keys in its widget and flashes it (`fieldRevealed`). A field that doesn't apply now says so."""
        row = self._param(name)
        if row is None:
            self._fail(f'Error: reveal: "{name}" is not a setting of this item.')
            return False
        if not row["holds"]:
            self._set_status(f"{row['label']} doesn't apply right now")
            return False
        if self._kit.search.strip() and not row["valid"]:
            self.setSearch("")
            row = self._param(name)
        if row.get("in"):
            self._kit.open_groups[row["in"]] = True
            self._refresh()
        elif "in" not in row and not row["valid"]:      # behind the More row
            self.toggleMore()
        self.fieldRevealed.emit(name)
        return True

    def _param(self, name):
        return next((r for r in self.model.rows if r["row"] == "param" and r["id"] == name), None)
