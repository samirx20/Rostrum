"""The keys picked in the timeline (UX_SPEC 3.17 "Select, move …", INTERACTION 1.3, the list rule): click picks one,
Ctrl+click adds or removes one, Shift+click picks the run between on the same row. A diamond on a layer's bar stands
for every key of that layer at that frame, so it picks them all. Picked keys move together (one drag = one change),
Delete removes them (one change), Esc lets go of them before the layers (the Esc ladder). Screen state, never the
document; offered to QML as `backend.keys` (the kit's `attach`).

Keys never enter the kit's one selection (UX_SPEC 3.18 decision 5): the selection is the layers the keys belong to, so
the settings panel keeps showing the layer (the keyed settings highlighted: `props`) and the key bar alone shows the
keys. This set is its own state: Delete removes keys, not layers, while it holds any; picking other layers (or a
click on a row's empty part, or Esc) lets them go.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui.pending import finish_typing

from .bounds import layer_of
from .key_moves import KeyMoves


class KeySelect(KeyMoves, QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._ids, self._drag, self._own = bridge, [], None, False
        self._found, self._anchor = [], 0.0                 # a drag's snap targets and the grabbed key's time (key_moves.py)
        bridge.selectedItemsChanged.connect(self._followed)
        bridge.docChanged.connect(self._prune)

    # ---- reads ------------------------------------------------------------------------------------------------
    @Property("QVariantList", notify=changed)
    def ids(self):
        return list(self._ids)

    @Property(int, notify=changed)
    def count(self):
        return len(self._ids)

    @Property("QVariantList", notify=changed)
    def props(self):
        """The settings the picked keys animate on the selected layer itself: its panel highlights those rows."""
        layer = self.b.selectedLayer
        return sorted({self.b.doc.item(k)["prop"] for k in self._ids
                       if self.b.doc.has(k) and self.b.doc.parent_of(k)[0] == layer})

    @Slot("QVariantList", result=bool)
    def has(self, ids):
        return bool(ids) and all(i in self._ids for i in ids)

    # ---- picking ----------------------------------------------------------------------------------------------
    @Slot("QVariantList", str, "QVariantList")
    def click(self, ids, how, row):
        """ids: the keys one diamond stands for; how: "" | "ctrl" | "shift"; row: every diamond's ids on its row, in
        time order (for Shift's run)."""
        ids = [str(i) for i in ids]
        if how == "ctrl":
            now = [i for i in self._ids if i not in ids] if self.has(ids) else self._ids + [i for i in ids if i not in self._ids]
        elif how == "shift" and self._ids:
            flat = [[str(i) for i in group] for group in row]
            at = [n for n, g in enumerate(flat) if any(i in self._ids for i in g)]
            here = next((n for n, g in enumerate(flat) if ids[0] in g), None)
            if at and here is not None:
                lo, hi = min(at[0], here), max(at[-1], here)
                now = self._ids + [i for g in flat[lo:hi + 1] for i in g if i not in self._ids]
            else:
                now = ids
        else:
            now = ids
        self._set(now)

    @Slot("QVariantList", str)
    def box(self, groups, how):
        """A box dragged over the timeline: every key it touches (groups: each diamond's ids). Ctrl or Shift adds
        them to the keys already picked (INTERACTION 1.3: a box picks what it touches)."""
        ids = [str(i) for g in groups for i in g]
        self._set(self._ids + ids if how in ("ctrl", "shift") else ids)

    @Slot()
    def clear(self):
        self._set([])

    def _set(self, ids):
        ids = list(dict.fromkeys(ids))
        if ids != self._ids:
            finish_typing()                            # a Key field's typing lands on the keys it was typed for (pending.py)
        self._ids = ids
        layers = self._layers()
        if layers and set(layers) != set(self.b.selected_layers()):
            self._own = True                           # the keys' layers become the selection; the keys stay picked
            try:
                self.b.selectMany(layers)
            finally:
                self._own = False
        self.changed.emit()

    def _layers(self):
        return list(dict.fromkeys(layer_of(self.b.doc, k) for k in self._ids if self.b.doc.has(k)))

    def _followed(self):
        """Other layers (or nothing) picked: the keys are let go. A change that keeps the same layers keeps them."""
        if self._ids and not self._own and set(self._layers()) != set(self.b.selected_layers()):
            self._ids = []
            self.changed.emit()

    def _prune(self):
        gone = [i for i in self._ids if not self.b.doc.has(i)]
        if gone:
            self._ids = [i for i in self._ids if i not in gone]
            self.changed.emit()

    # ---- acting -----------------------------------------------------------------------------------------------
    @Slot(result=bool)
    def remove(self):
        """Delete: the picked keys go, one change."""
        if not self._ids:
            return False
        ids, self._ids = list(self._ids), []
        n = len(ids)
        ok = self.b.guard(lambda: self.b.done(self.b.doc.apply([{"op": "key.remove", "target": ids, "args": {}}], self.b.who,
                                                               label="Delete key" if n == 1 else f"Delete {n} keys"), ""))
        self.changed.emit()
        return ok
