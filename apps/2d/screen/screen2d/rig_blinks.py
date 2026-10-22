"""Add blinks… (UX_SPEC 3.23 › Blinks; `backend.blinks`, qml/BlinkSheet.qml): select an eyes swap set → the context
bar's Add blinks… opens a small sheet: how often (seconds), how much the gaps vary, which drawing is open, closed and
half closed (guessed from their names: rig_mouths.closed_of). Apply = one `blink.add` change over the whole scene: hold
keys on the set's Shows that the person moves like any other. The sheet remembers the last amounts.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d.names import display_name

from . import rig_mouths


class BlinkSheet(QObject):
    changed = Signal()
    opened = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._set, self._every, self._vary = bridge, "", 3.5, 0.3
        self._open = self._closed = self._half = ""

    @Property(bool, notify=changed)
    def open(self):
        return bool(self._set)

    @Property(str, notify=changed)
    def what(self):
        return display_name(self.b.doc.item(self._set)) if self._set and self.b.doc.has(self._set) else ""

    @Property(float, notify=changed)
    def every(self):
        return self._every

    @Property(float, notify=changed)
    def vary(self):
        return self._vary

    @Property("QVariantMap", notify=changed)
    def picks(self):
        """{open, closed, half}: the drawings (ids)."""
        return {"open": self._open, "closed": self._closed, "half": self._half}

    @Property("QVariantList", notify=changed)
    def options(self):
        kids = self.b.doc.item(self._set).get("layers", []) if self._set else []
        return [{"value": k["id"], "label": display_name(k)} for k in kids]

    @Slot(result=bool)
    def start(self):
        sel = self.b.selected_layers()
        item = self.b.doc.item(sel[0]) if len(sel) == 1 else None
        if not item or not item.get("swap") or len(item.get("layers", [])) < 2:
            self.b._set_status("Add blinks needs one swap set of two or more eye drawings selected.")
            return False
        self._set = item["id"]
        self._open, self._closed, self._half = rig_mouths.closed_of(item["layers"])
        self.changed.emit()
        self.opened.emit()
        return True

    @Slot(float)
    def setEvery(self, s):
        self._every = max(0.1, min(60.0, float(s)))
        self.changed.emit()

    @Slot(float)
    def setVary(self, v):
        self._vary = max(0.0, min(1.0, float(v)))
        self.changed.emit()

    @Slot(str, str)
    def setPick(self, which, layer):
        """Which drawing is open / closed / half closed ("" for half = none)."""
        setattr(self, "_" + which, layer)
        self.changed.emit()

    @Slot()
    def apply(self):
        if not self._set or not self._open or not self._closed or self._open == self._closed:
            return self.b._set_status("Pick an open and a closed drawing (two different ones).")
        args = {"open": self._open, "closed": self._closed, "every": round(self._every, 3), "vary": round(self._vary, 3),
                **({"half": self._half} if self._half and self._half not in (self._open, self._closed) else {})}
        call = {"op": "blink.add", "target": [self._set], "args": args}
        if self.b.guard(lambda: self.b._apply([call], f"Blinks on {self.what}")):
            self.close()

    @Slot()
    def close(self):
        self._set = ""
        self.changed.emit()
