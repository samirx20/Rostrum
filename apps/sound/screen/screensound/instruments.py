"""The Instruments page: one card per track that has an instrument. Exposed to QML as `instruments`.

Each card is a list of the same generic rows the inspector uses (`cards.layout` + `rostrum_gui.rows`), kept in
one RowsModel per card so a control appearing or leaving eases in place. Editing a card's control is the
bridge's edit on that track (the card selects its track first), so it is one operation, one history entry.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui import rows
from rostrum_gui.model import RowsModel

from . import cards

ROLES = ("id", "name", "what", "controls", "moreOpen")


class InstrumentsPage(QObject):
    emptyChanged = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge, self.doc = bridge, bridge.doc
        self._layout = cards.layout(self.doc.kind.registry.field_op("track"))
        self._more: set[str] = set()
        self._controls: dict[str, RowsModel] = {}
        self._cards = RowsModel(ROLES, self)
        self._refresh()
        bridge.docChanged.connect(self._refresh)

    @Property(QObject, constant=True)
    def cards(self):
        return self._cards

    @Property(bool, notify=emptyChanged)
    def empty(self):
        return not self._cards.rows

    @Slot(str)
    def toggleMore(self, track_id):
        self._more ^= {track_id}
        self._refresh()

    def _refresh(self):
        had = bool(self._cards.rows)
        tracks = [t for t in self.doc.items() if t["type"] == "track" and cards.has_instrument(t)]
        self._more &= {t["id"] for t in tracks}
        out = []
        for t in tracks:
            model = self._controls.setdefault(t["id"], RowsModel(rows.ROLES, self))
            evaluated = cards.evaluate(self.doc, self._layout, t, t["id"] in self._more)
            model.update(evaluated) if model.rows else model.reset(evaluated)
            out.append({"id": t["id"], "name": self.bridge.label_of(t), "what": cards.what_it_is(t),
                        "controls": model, "moreOpen": t["id"] in self._more})
        self._cards.update(out)
        if had != bool(out):
            self.emptyChanged.emit()
