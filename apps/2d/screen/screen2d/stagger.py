"""Stagger… (UX_SPEC 3.19, INTERACTION 1.2 point 5): select layers → the context bar's Stagger… opens a small popover
("Each starts [2 f] after the one before", Order). The bars and keys spread live while the number or the order
changes (one open gesture: layer.stagger previewed), and clicking away keeps it as ONE change; Esc takes it back.
The popover remembers the last amount and order. Opening it again re-spreads from the first (layer.stagger counts
from the earliest start). With keys picked on two or more layers it staggers those keys instead (key.stagger: each
layer's picked keys move together). Offered to QML as `backend.stagger`; screen state only.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d.ops_stagger import ORDERS, WORDS
from rostrum_gui.edits import Drag


class Stagger(QObject):
    changed = Signal()
    opened = Signal()               # QML opens the popover (the action's `do`)

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._drag, self._ids, self._by, self._order = bridge, None, [], 2, "stack"
        self._op, self._what = "layer.stagger", ""

    @Property(bool, notify=changed)
    def open(self):
        return self._drag is not None

    @Property(int, notify=changed)
    def by(self):
        """Frames between one start and the next."""
        return self._by

    @Property(str, notify=changed)
    def order(self):
        return self._order

    @Property("QVariantList", constant=True)
    def orders(self):
        return [{"value": o, "label": WORDS[o]} for o in ORDERS]

    @Property(str, notify=changed)
    def what(self):
        return self._what

    @Slot(result=bool)
    def start(self):
        """Open it on the selected layers (two or more): the spread shows at once with the last amount and order."""
        self.end()
        keys, layers = self.b._keys.ids, self.b.selected_layers()
        if keys and len(self.b._keys._layers()) >= 2:          # keys picked on several layers: those keys
            self._op, self._ids = "key.stagger", keys
            self._what = f"{len(keys)} keys on {len(self.b._keys._layers())} layers"
        elif len(layers) >= 2:
            self._op, self._ids, self._what = "layer.stagger", layers, f"{len(layers)} layers"
        else:
            self.b._set_status("Stagger needs two or more layers selected, or keys picked on two or more layers.")
            return False
        label = f"Stagger {self._what}"

        def go():
            self._drag = Drag(self.b.doc, self.b.who, label)
        if not self.b.guard(go):
            return False
        self._spread()
        self.opened.emit()
        return True

    @Slot(int)
    def setBy(self, frames):
        self._by = max(0, int(frames))
        self._spread()

    @Slot(str)
    def setOrder(self, order):
        if order in ORDERS:
            self._order = order
            self._spread()

    def _spread(self):
        if self._drag is not None:
            call = {"op": self._op, "target": self._ids,
                    "args": {"by": round(self._by / self.b.comp()["fps"], 6), "order": self._order}}
            self.b.guard(lambda: self._drag.preview([call]))
        self.changed.emit()

    @Slot()
    def end(self):
        """Click away / Enter: keep it (one change)."""
        d, self._drag = self._drag, None
        if d is not None:
            self.b.guard(lambda: self.b.done(d.end(), ""))
            self.changed.emit()

    @Slot()
    def cancel(self):
        """Esc: the layers go back to where they were (nothing recorded)."""
        d, self._drag = self._drag, None
        if d is not None:
            self.b.guard(lambda: d.end(cancel=True))
            self.b._set_status("Stagger cancelled")
            self.changed.emit()
