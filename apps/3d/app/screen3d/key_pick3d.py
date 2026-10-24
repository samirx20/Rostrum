"""The keys picked on 3D's timeline (`backend.keys`, the kit's KeyDot.qml and box pick), the key's Ease list
(`backend.keyBar`) and the selected rows (`backend.multi`). Screen state, never the document.

Click a diamond: its keys are picked; one key alone is also the selection, so the settings panel shows that key (its
time, value and ease). Ctrl+click adds or takes out, Shift+click the run between on the row, a box on a row's empty part
picks what it touches. Picked keys move together (timeline3d.py: one drag = one change). Picking another item lets
them go. Every change is an operation (key.set).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui import eases


class KeyPick3D(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._ids, self._own = bridge, [], False
        bridge.selectedItemsChanged.connect(self._followed)
        bridge.docChanged.connect(self._prune)

    ids = Property("QVariantList", lambda self: list(self._ids), notify=changed)
    count = Property(int, lambda self: len(self._ids), notify=changed)

    @Slot("QVariantList", result=bool)
    def has(self, ids):
        return bool(ids) and all(i in self._ids for i in ids)

    @Slot("QVariantList", str, "QVariantList")
    def click(self, ids, how, row):
        """ids: the keys one diamond stands for; how: "" | "ctrl" | "shift"; row: every diamond's ids on its row."""
        ids = [str(i) for i in ids]
        if how == "ctrl":
            now = [i for i in self._ids if i not in ids] if self.has(ids) else self._ids + ids
        elif how == "shift" and self._ids:
            flat = [[str(i) for i in g] for g in row]
            at = [n for n, g in enumerate(flat) if any(i in self._ids for i in g)]
            here = next((n for n, g in enumerate(flat) if ids[0] in g), None)
            now = self._ids + [i for g in flat[min(at[0], here):max(at[-1], here) + 1] for i in g] if at and here is not None else ids
        else:
            now = ids
        self._set(now)

    @Slot("QVariantList", str)
    def box(self, groups, how):
        ids = [str(i) for g in groups for i in g]
        self._set(self._ids + ids if how in ("ctrl", "shift") else ids)

    @Slot()
    def clear(self):
        if self._ids:
            self._ids = []
            self.changed.emit()

    @Slot(str, float, result=bool)
    def beginStretch(self, key_id, t):
        """Alt+press on the first or last picked key: dragging stretches the picked keys in time (timeline3d.py, key.scale)."""
        return self.b._mover.begin_stretch(list(self._ids), key_id, t)

    @Slot(str, float, result=bool)
    def beginDrag(self, key_id, t):
        return self.b.beginMove(list(self._ids), key_id, "Move keys")

    @Slot(float, float)
    def dragTo(self, t, reach):
        self.b.keyDragTo(t, reach)

    @Slot()
    def endDrag(self):
        self.b.endDrag()

    def _set(self, ids):
        self._ids = [i for i in dict.fromkeys(ids) if self.b.doc.has(i)]
        owners = list(dict.fromkeys(self.b.doc.parent_of(k)[0] for k in self._ids))
        self._own = True
        try:     # one key: it is the selection (the panel shows it); several: their (first) item
            self.b.select(self._ids[0] if len(self._ids) == 1 else owners[0] if owners else self.b.selected)
        finally:
            self._own = False
        self.changed.emit()

    def _followed(self):
        if self._ids and not self._own and self.b.selectedOwner not in {self.b.doc.parent_of(k)[0] for k in self._ids}:
            self.clear()

    def _prune(self):
        if any(not self.b.doc.has(i) for i in self._ids):
            self._ids = [i for i in self._ids if self.b.doc.has(i)]
            self.changed.emit()


class KeyBar3D(QObject):
    """A key's right-click Ease list (LayerTimeline.qml's menu): every picked key gets the ease, one change (key.set)."""
    changed = Signal()
    menuAsked = Signal(float, float)

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b = bridge

    eases = Property("QVariantList", lambda self: [{"value": e["value"], "label": e["label"]} for e in eases.EASES], constant=True)
    easeOnKey = Property(bool, lambda self: True, constant=True)    # a key's right-click is the Ease list (the kit's KeyDot.qml)

    @Slot(float, float)
    def askMenu(self, x, y):
        """Right-click on a key: the Ease list at this window point (LayerTimeline.qml)."""
        self.menuAsked.emit(x, y)

    @Slot(str, result=bool)
    def setEase(self, ease):
        ids = list(self.b.keys.ids)
        return bool(ids) and self.b._guard(lambda: self.b._done(self.b.doc.apply(
            [{"op": "key.set", "target": ids, "args": {"ease": ease}}], self.b.who, label=f"Ease: {eases.label_of(ease)}"), ""))


class Multi3D(QObject):
    """The scene items selected together (the timeline lights every selected item's bar)."""
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b = bridge
        bridge.outlineChanged.connect(self.changed)

    ids = Property("QVariantList", lambda self: self.b.selectedRows, notify=changed)

    @Slot(str, result=bool)
    def has(self, item_id):
        return item_id in self.b.selectedRows
