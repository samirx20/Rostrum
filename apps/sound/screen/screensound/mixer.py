"""The Mix page: one strip per track, one per bus, then the master. Exposed to QML as `mixer`.

Strips come from the document (`strips.py`) and the last render's meters; every edit is the bridge's edit on the
strip's item (the strip selects it first), so a fader drag is one scrub = one change. Adding an effect is the
`effect.add` operation, then the new effect is selected so the inspector edits it.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui import rows
from rostrum_gui.model import RowsModel

from . import strips
from .listen_pics import ListenPics

ROLES = ("id", "name", "volume", "pan", "mute", "solo", "effects", "meter", "canSolo", "output", "outputId", "outputs",
         "sends", "sendTargets")


class MixPage(QObject):
    masterChanged = Signal()

    def __init__(self, bridge, pics_folder=None, parent=None):
        super().__init__(parent)
        self.bridge, self.doc = bridge, bridge.doc
        self._tracks = RowsModel(ROLES, self)
        self._buses = RowsModel(ROLES, self)
        self._master_rows = RowsModel(rows.ROLES, self)
        self._master_layout = strips.master_layout(self.doc.kind.registry.field_op("master"))
        self._master: dict = {}
        self.pics = ListenPics(bridge, pics_folder, self)
        self._refresh()
        bridge.docChanged.connect(self._refresh)
        bridge.renderChanged.connect(self._refresh)

    def close(self):
        self.pics.close()

    @Property(QObject, constant=True)
    def tracks(self):
        return self._tracks

    @Property(QObject, constant=True)
    def buses(self):
        return self._buses

    @Property(QObject, constant=True)
    def masterRows(self):
        return self._master_rows

    @Property("QVariantMap", notify=masterChanged)
    def master(self):
        return self._master

    @Property(QObject, constant=True)
    def listen(self):
        return self.pics

    @Property("QVariantList", constant=True)
    def effectTypes(self):
        return list(self.doc.kind.registry.get("effect.add").param("effect").options)

    @Slot(str, str, result=bool)
    def addEffect(self, item_id, effect_type):
        """effect.add on that track or the master (one change), then select the new effect."""
        self.bridge.select(item_id)
        if not self.bridge.run("effect.add:" + effect_type):
            return False
        self.bridge.select(self.doc.item(item_id)["effects"][-1]["id"])
        return True

    @Slot(result=bool)
    def addBus(self):
        """bus.add (one change), then select the new bus so the inspector can name it."""
        before = {b["id"] for b in self._bus_items()}
        if not self._call({"op": "bus.add", "args": {}}, "Add bus"):
            return False
        self.bridge.select(next(b["id"] for b in self._bus_items() if b["id"] not in before))
        return True

    @Slot(str, str, result=bool)
    def addSend(self, track_id, bus_id):
        """send.add from a track to a bus (one change), then select the send (its level is the first control)."""
        if not self._call({"op": "send.add", "target": [track_id], "args": {"bus": bus_id}}, "Add send"):
            return False
        self.bridge.select(f"{track_id}.send_{bus_id}")
        return True

    @Slot(str, str, result=bool)
    def setOutput(self, item_id, bus_id):
        """Play a track or bus to the master ("master") or to a bus: its `output` field, one change."""
        kind = self.doc.item(item_id)["type"]
        return self._call({"op": f"{kind}.set", "target": [item_id], "args": {"output": bus_id}}, "Route")

    def _call(self, call, label):
        return self.bridge._guard(lambda: self.bridge._apply([call], label))

    def _bus_items(self):
        return [b for b in self.doc.items() if b["type"] == "bus"]

    def _refresh(self):
        render = dict(self.bridge.lastRender or {})
        label = self.bridge.label_of
        buses = self._bus_items()
        self._tracks.update([strips.strip(t, label(t), strips.meter_of(render, t["id"]),
                                          strips.routing(t, buses, label))
                             for t in self.doc.items() if t["type"] == "track"])
        self._buses.update([strips.strip(b, label(b), strips.meter_of(render, b["id"]), strips.routing(b, buses, label))
                            for b in buses])
        m = self.doc.item(strips.MASTER)
        self._master = strips.strip(m, "Master", strips.master_meter(render))
        self.masterChanged.emit()
        evaluated = rows.evaluate(self._master_layout, m, self.doc.kind.facts(m, self.doc), False)
        self._master_rows.update(evaluated) if self._master_rows.rows else self._master_rows.reset(evaluated)
