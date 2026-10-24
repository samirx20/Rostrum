"""The marker edits' bookkeeping. Undo / Redo, their labels and the top bar's "N changes" are the kit's
(DocBridge: bridge_review.py, changes_since_open), one rule across the document and the markers.
"""
from __future__ import annotations


class UndoState:
    """Mix-in for Bridge2D."""

    def _marker_saved(self):
        """A marker edit of this person's goes straight to the project's marker file, so the title never gets the
        "unsaved" dot for it: the top bar's "Saved · N changes" already says so (no second "saved" beside it)."""
        c = self.marks.last_change()
        self._marker_seen = c.seq if c is not None else 0
