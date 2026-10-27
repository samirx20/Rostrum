"""History's "go back to here" for the Sound window: a row of the History sheet (rostrum_gui history_rows: `seq`, `doc`)
makes the song stand as right after that step, by taking back the steps since (rostrum_sound.history_go). One new step
by the person, undoable; the steps after it stay in History, taken back, until brought back by going to a later row."""
from __future__ import annotations

from PySide6.QtCore import Slot

from rostrum_sound import history_go


class HistorySlots:
    @Slot(int, int, result=bool)
    def goToStep(self, seq, doc):
        """Go back (or forward) to step `seq` of document `doc` (a History row's fields)."""
        def go():
            d = self._review_docs()[doc]
            made = history_go.go_to(d, seq, self.who)
            self._stepped([d])
            self._set_status(made[-1].label if made else "Already there")
        return self._guard(go)
