"""The person's one history across documents edited from one screen (a mix-in for DocBridge): the document's own, then
each joined partner's (e.g. the shared markers), for Undo / Redo (bridge_edits) and the top bar's change count.
State: `self._kit.partners` and `self._kit.opened` (kit_state.py).
"""
from __future__ import annotations

from rostrum_core.history import History

_NONE = History({})                         # a joined partner that has no document yet


class HistoryParts:
    def changes_since_open(self) -> int:
        """The top bar's "N changes": how far the document and every joined partner (e.g. the markers) have moved
        since this window opened. A new or just-opened file shows none; Undo takes the count down, Redo brings it
        back (History.moved_since)."""
        return sum(h.moved_since(m) for h, m in zip(self._joined(), self._kit.opened))

    def _joined(self):
        """The histories in this person's one history now: the document's, then each partner's (an empty one for a
        partner with no document yet, e.g. no marker file)."""
        docs = [p.history_doc() for p in self._kit.partners]
        return [self.doc.history] + [d.history if d is not None else _NONE for d in docs]

    def open_item(self, item_id):
        """A document a step across documents reached that isn't joined here (rostrum_core.desk / joint.py), opened
        live for Undo / Redo; None = this app can't open it, and the undo is refused in words. Apps override."""
        return None

    def join_history(self, partner):
        """Another document edited from this screen joins the one undo history and the change count (AGENTS.md
        rule 3; rostrum_core.desk). `partner`: `history_doc()` (its Document now, or None), `stepped(doc)` (save and
        re-read after an undo / redo there), `last_change()` and a `changed` signal."""
        self._kit.partners.append(partner)
        d = partner.history_doc()
        self._kit.opened.append(d.history.mark() if d is not None else _NONE.mark())
        partner.changed.connect(lambda: self._heard(partner.last_change(), partner.history_doc()))
