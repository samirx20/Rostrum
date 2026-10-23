"""The timeline's rows (`layers`, outline.rows): worked out once per document state, markers and folds, and announced
(`layersChanged`) only when they really differ. QML's timeline is a ListView over this list, so every announcement
rebuilds every row; before, each document change, scrub frame and selection announced it (outlineChanged), and a
canvas drag rebuilt the whole timeline on every pointer move although its rows stayed the same.

A slot mix-in for Bridge2D (it declares `layersChanged`; outlineChanged and marker edits call `_layers_check`).
"""
from __future__ import annotations

from . import outline


class TimelineRows:
    _rows_at = None          # (placed, folds, A-opened, rows): the rows of that state
    _rows_told = None        # the rows QML was last told about

    def layer_rows(self) -> list[dict]:
        """The timeline's rows as the document is now (read by QML's `layers` and by the screen's own code)."""
        placed, flipped, only = self.placed(), frozenset(self._flipped), frozenset(self._anim_only)
        got = self._rows_at
        if got is None or got[0] is not placed or got[1] != flipped or got[2] != only:
            got = self._rows_at = (placed, flipped, only, outline.rows(placed, self._flipped, self._anim_only))
        return got[3]

    def _layers_check(self):
        """Something the rows may depend on changed: tell QML only when they differ from what it shows."""
        rows, told = self.layer_rows(), self._rows_told
        self._rows_told = rows
        if rows != told:
            self.layersChanged.emit()
