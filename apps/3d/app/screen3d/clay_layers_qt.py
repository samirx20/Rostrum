"""The Clay panel's sculpt layers (PR4; rostrum3d/clay_layers.py), for QML as `viewport.clay.layersObj`.

- `items`: the Base, then the selected clay's layers, each its name, whether it is on, and whether the next stroke goes
  on it (`chosen`). Absent until the clay has a layer: the Steps head's "+ Layer" makes the first (claylayer.add).
- `rows`: the chosen layer's Amount (the kit's InspectorRow: drag, type, scrub, and its key mark: K keys it at the
  playhead, a face shape), `claylayer.set` on that layer.
- `choose`: where the next stroke goes (clay.set sculptLayer, "" = the Base); `toggleOn`, `rename`, `bake`, `remove`:
  claylayer.set on / name, claylayer.bake, claylayer.remove. One undo step each, the calls agents make.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui.model import RowsModel

from .clay_steps_qt import StepRows

ROLES = ("id", "label", "on", "chosen", "amount")
BASE = "Base"


class ClayLayers(QObject):
    changed = Signal()

    def __init__(self, tool):
        super().__init__(tool)
        self.t, self.b = tool, tool.b
        self.model = RowsModel(ROLES, self)
        self.amountRows = StepRows(self.b, ["amount"], self, kind="claylayer")
        self.b.docChanged.connect(self.refresh)
        self.b.selectionChanged.connect(self.refresh)
        self.b.frameChanged.connect(lambda: self.refresh() if self._layers() else None)   # a keyed Amount at the playhead
        self.refresh()

    def _clay(self):
        return self.t._item()

    def _layers(self) -> list[dict]:
        clay = self._clay()
        return (clay.get("sculptLayers") or []) if clay is not None else []

    def _next(self) -> str:
        clay = self._clay()
        return (clay.get("sculptLayer") or "") if clay is not None else ""

    def refresh(self, *_):
        lays, now = self._layers(), self._next()
        rows = [{"id": "", "label": BASE, "on": True, "chosen": now == "", "amount": ""}] if lays else []
        rows += [{"id": x["id"], "label": x.get("name") or x["id"], "on": bool(x.get("on", True)),
                  "chosen": x["id"] == now, "amount": f"{round(100 * float(self.b.shown_values(x).get('amount', 1.0)))} %"} for x in lays]
        self.model.update(rows)
        self.amountRows.pick(next((x for x in lays if x["id"] == now), None))
        self.changed.emit()

    items = Property(QObject, lambda s: s.model, constant=True)
    rows = Property(QObject, lambda s: s.amountRows, constant=True)
    count = Property(int, lambda s: len(s._layers()), notify=changed)
    chosen = Property(str, lambda s: s._next(), notify=changed)

    def _apply(self, calls: list, label: str):
        self.b._guard(lambda: self.b._apply(calls, label))

    @Slot()
    def add(self):
        clay = self._clay()
        if clay is not None:
            self._apply([{"op": "claylayer.add", "target": [clay["id"]], "args": {}}], "New sculpt layer")

    @Slot(str)
    def choose(self, layer_id):
        clay = self._clay()
        if clay is not None and layer_id != self._next():
            self._apply([{"op": "clay.set", "target": [clay["id"]], "args": {"sculptLayer": layer_id}}],
                        "Sculpt on " + (self.b.doc.item(layer_id).get("name") if layer_id else BASE))

    @Slot(str)
    def toggleOn(self, layer_id):
        on = bool(self.b.doc.item(layer_id).get("on", True))
        self._apply([{"op": "claylayer.set", "target": [layer_id], "args": {"on": not on}}],
                    "Layer off" if on else "Layer on")

    @Slot(str, str)
    def rename(self, layer_id, name):
        if name.strip() and name.strip() != self.b.doc.item(layer_id).get("name"):
            self._apply([{"op": "claylayer.set", "target": [layer_id], "args": {"name": name.strip()}}], "Rename layer")

    @Slot(str)
    def bake(self, layer_id):
        self._apply([{"op": "claylayer.bake", "target": [layer_id], "args": {}}], "Bake layer")

    @Slot(str)
    def remove(self, layer_id):
        self._apply([{"op": "claylayer.remove", "target": [layer_id], "args": {}}], "Remove layer")
