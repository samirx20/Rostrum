"""The marker edits' "saved" note. Undo / Redo, their labels and the top bar's "N changes" are the kit's
(DocBridge: bridge_review.py, changes_since_open), one rule across the document and the markers.
"""
from __future__ import annotations


class UndoState:
    """Mix-in for Bridge2D."""

    def _marker_saved(self):
        """A marker edit of this person's goes straight to the project's marker file, so the title never gets the
        "unsaved" dot for it (the dot is for the document). Say so instead, so no one thinks it still needs Save (kept short: the top bar has little room beside the page tabs)."""
        c = self.marks.last_change()
        if c is not None and c.who == self.who and c.seq != getattr(self, "_marker_seen", c.seq):
            self._set_status(f"{c.label}  ·  saved")
        self._marker_seen = c.seq if c is not None else 0
