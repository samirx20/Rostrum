"""The Mixer (bottom dock): one strip per track, one per bus, then the master. Exposed to QML as `mixer`.

Strips come from the document (`strips.py`) and the last render's meters; `live` is every strip's level while the
song plays ({id: [peak dB, RMS dB]}, the engine's `levels` lines: the render's own levels at the speaker's time),
replaced as each line arrives (MixMeter.qml animates the fall and the held peak); every edit is the bridge's edit on the
strip's item (the strip selects it first), so a fader drag is one scrub = one change. Adding an effect is the
`effect.add` operation, then the new effect is selected so the inspector edits it.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui.model import RowsModel

from . import ducks, playback, problems, strips, timeline
from .cleaning import CleanedTake
from .export import RenderExport
from .loudness import LoudnessMeter
from .plugins import PluginHub

ROLES = ("id", "name", "reverb", "hue", "volume", "pan", "mute", "solo", "effects", "meter", "canSolo", "canArm", "canMute", "canPan",
         "output", "outputId", "outputs", "sends", "sendTargets", "ducks", "duckTargets")


class MixPage(QObject):
    masterChanged = Signal()
    liveChanged = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge, self.doc = bridge, bridge.doc
        self._tracks = RowsModel(ROLES, self)
        self._buses = RowsModel(ROLES, self)
        self._master: dict = {}
        self._live: dict = {}
        self._peaks: dict = {}
        self._seen: dict = {}            # id -> the item each strip was made from (a drag's step makes only changed ones)
        bridge.transport.player.levels.connect(self._levels)
        self._plugins = PluginHub(bridge, playback.open_engine, self)
        self._ducks, self._loudness = ducks.DuckHub(bridge, self), LoudnessMeter(bridge, self)
        self._export, self._cleaning = RenderExport(bridge, self._loudness, parent=self), CleanedTake(bridge, self)
        bridge.mix = self                                 # the scripted steps (steps.py) reach these through the bridge
        self._problems = problems.make(bridge, self._cleaning)
        bridge.exporter, bridge.problems = self._export, self._problems   # the kit's sheet, chips and steps (EXPORT.md)
        self._refresh()
        self._plugins.catalogChanged.connect(self._refresh)      # the scan names the vendors the chips drop
        bridge.docChanged.connect(self._refresh)
        bridge.docStepped.connect(self._stepped)               # the strips follow a fader drag live
        bridge.renderChanged.connect(self._refresh)

    def close(self):
        self._plugins.close()
        self._export.close()
        self._cleaning.close()

    @Property(QObject, constant=True)
    def plugins(self):
        return self._plugins

    @Property(QObject, constant=True)
    def ducks(self):
        return self._ducks

    @Property(QObject, constant=True)
    def loudness(self):
        return self._loudness

    @Property(QObject, constant=True)
    def export(self):
        return self._export

    @Property(QObject, constant=True)
    def problems(self):
        """The Problems chip's list (problems.py)."""
        return self._problems

    @Property(QObject, constant=True)
    def cleaning(self):
        return self._cleaning

    @Property(QObject, constant=True)
    def tracks(self):
        return self._tracks

    @Property(QObject, constant=True)
    def buses(self):
        return self._buses

    @Property("QVariantMap", notify=masterChanged)
    def master(self):
        return self._master

    @Property("QVariantMap", notify=liveChanged)
    def live(self):
        return self._live

    @Property("QVariantMap", notify=liveChanged)
    def peaks(self):
        """{id: dBFS}: each strip's highest peak since play started, held after the stop until the next play."""
        return self._peaks

    def _levels(self, strips_now: dict):
        if strips_now:
            self._peaks = strips.held_peaks(self._peaks, strips_now, fresh=not self._live)
        self._live = strips_now
        self.liveChanged.emit()

    @Property("QVariantList", constant=True)
    def effectTypes(self):
        """The built-in effect types; a plug-in is chosen from the scan (`plugins`), not from this list."""
        return [t for t in self.doc.kind.registry.get("effect.add").param("effect").options if t != "plugin"]

    @Slot(str, str, result=bool)
    def addEffect(self, item_id, effect_type):
        """effect.add on that track or the master (one change), then select the new effect."""
        self.bridge.select(item_id)
        if not self._call({"op": "effect.add", "target": [item_id], "args": {"effect": effect_type}}, "Add " + strips.effect_name(effect_type)):
            return False
        self.bridge.select(self.doc.item(item_id)["effects"][-1]["id"])
        return True

    @Slot(result=bool)
    def addBus(self):
        """bus.add (one change), then select the new bus so the inspector can name it."""
        before = {b["id"] for b in self._bus_items()}
        if not self._call({"op": "bus.add", "args": {}}, "Add group"):
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
        return list(self.doc.data.get("buses", []))

    def _refresh(self, only=None):
        """Make the strips again. `only` (a set of ids): a drag's step, only those strips; the rest keep theirs."""
        render, root = dict(self.bridge.lastRender or {}), self.doc.data
        label = self.bridge.label_of
        buses, vendor, tracks = self._bus_items(), self._plugins.vendor_of, list(root.get("tracks", []))
        m = self.doc.item(strips.MASTER)
        self._seen = {i["id"]: i for i in [*tracks, *buses, m]}
        old = {r["id"]: r for r in [*self._tracks.rows, *self._buses.rows]} if only is not None else {}

        def made(i, t):                          # a strip the step did not change: as it is
            return old.get(t["id"]) if only is not None and t["id"] not in only else None
        # `instant`: a strip that came or went is inserted or removed and every other strip keeps its delegate (a
        # reset made every strip again: ~200 ms for one track added to a 6-track song).
        self._tracks.update([made(i, t) or strips.strip(t, label(t), strips.meter_of(render, t["id"]),
                                                         {**strips.routing(t, buses, label), **ducks.strip_ducks(t, tracks, label)},
                                                         vendor, timeline.hue(t, i))
                             for i, t in enumerate(tracks)], instant=True)
        self._buses.update([made(i, b) or strips.strip(b, label(b), strips.meter_of(render, b["id"]), strips.routing(b, buses, label), vendor)
                            for i, b in enumerate(buses)], instant=True)
        master = strips.strip(m, "Master", strips.master_meter(render), vendor_of=vendor)
        if master != self._master:                # the Master strip reads a map: only news re-runs its bindings
            self._master = master
            self.masterChanged.emit()

    def _stepped(self):
        """A drag's step (a fader, a pan, a knob): only the strips whose item it changed are made again (the document
        is never changed in place: an untouched item is the same object). Strips that came or went: all again."""
        root = self.doc.data
        now = [*root.get("tracks", []), *root.get("buses", []), self.doc.item(strips.MASTER)]
        if [i["id"] for i in now] != list(self._seen):
            return self._refresh()
        changed = {i["id"] for i in now if self._seen[i["id"]] is not i}
        if changed:
            self._refresh(changed)
