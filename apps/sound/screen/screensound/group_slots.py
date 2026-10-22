"""Folding groups in the arrangement: the person's own screen state (never the song, never undone, never saved);
`groups.py` draws it. Alt+click on a fold arrow folds or unfolds every group."""
from __future__ import annotations

from PySide6.QtCore import Slot


class GroupSlots:
    _folded: frozenset = frozenset()          # ids of the folded groups

    @Slot(str, bool)
    def toggleFold(self, bus_id, everyone):
        """Fold (or unfold) a group; with `everyone`, all groups: folded unless they all already are."""
        groups = [b["id"] for b in self.doc.data.get("buses", []) if any(
            x.get("output") == b["id"] for x in [*self.doc.data.get("tracks", []), *self.doc.data.get("buses", [])])]
        if everyone:
            self._folded = frozenset() if all(g in self._folded for g in groups) else frozenset(groups)
        else:
            self._folded = self._folded ^ {bus_id}
        self._rebuild()
