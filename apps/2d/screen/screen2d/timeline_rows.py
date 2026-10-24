"""The timeline's rows (`layers`, outline.rows): worked out once per document state, markers and folds, and announced
(`layersChanged`) only when they really differ. QML's timeline is a ListView over `rowsModel` / `rowsCompact`
(rostrum_gui/rows_model.py), which change row by row, so a row, and a key under the pointer, lives as long as its item
does; over the plain list every announcement rebuilt every row and a key drag lost its key at the first move.

A slot mix-in for Bridge2D (it declares `layersChanged`; outlineChanged and marker edits call `_layers_check`).
"""
from __future__ import annotations

from rostrum_gui import row_facts
from rostrum_gui.rows_model import RowsModel

from . import outline, painting_open


class TimelineRows:
    _rows_at = None          # (placed, folds, A-opened, rows): the rows of that state
    _rows_kept = None        # outline.rows' memory: a layer unchanged since the last rows keeps its rows
    _rows_told = None        # the rows QML was last told about
    _facts_told = None       # the row facts it was last told (row_facts.py)

    def layer_rows(self) -> list[dict]:
        """The timeline's rows as the document is now (read by QML's `layers` and by the screen's own code); a
        painting opened on its own: its one row (painting_open.row)."""
        opened = self._opened.item() if getattr(self, "_opened", None) is not None else None
        if opened is not None:
            c = self.comp()
            got = self._rows_at
            if got is None or got[0] is not opened or got[1:3] != (c["fps"], c["duration"]):
                got = self._rows_at = (opened, c["fps"], c["duration"], [painting_open.row(opened, c["fps"], c["duration"])])
            return got[3]
        placed, flipped, only = self.placed(), frozenset(self._flipped), frozenset(self._anim_only)
        got = self._rows_at
        if self._rows_kept is None:
            self._rows_kept = {}
        if got is None or got[0] is not placed or got[1] != flipped or got[2] != only:
            got = self._rows_at = (placed, flipped, only, outline.rows(placed, self._flipped, self._anim_only, self._rows_kept))
        return got[3]

    def _layers_check(self):
        """Something the rows may depend on changed: tell QML only when they differ from what it shows."""
        rows, told = self.layer_rows(), self._rows_told
        self._rows_told = rows
        if rows != told:
            facts = row_facts.of(rows)
            if facts != self._facts_told:
                self._facts_told = facts
                self.rowFactsChanged.emit()
            self.layersChanged.emit()
        if self._row_models:
            self._push_rows(rows)

    _row_models = None       # (all rows, the shown layer's row): made when QML first asks

    def _push_rows(self, rows):
        every, compact = self._row_models
        shown = self.selectedLayer or (rows[0]["id"] if rows else "")
        every.set(rows)
        compact.set([r for r in rows if r["row"] == "layer" and r["id"] == shown])

    def row_models(self):
        if self._row_models is None:
            self._row_models = (RowsModel(self), RowsModel(self))
            self._push_rows(self.layer_rows())
        return self._row_models
