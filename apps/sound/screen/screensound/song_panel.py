"""The song's own settings, exposed to QML as `songPanel`. The settings panel, shown while nothing is selected
(SongSettings.qml), lists the song's timeline (SongList.qml, song_list.py): every tempo, time signature and key
CHANGE, the sections and markers (a click selects one); the first tempo, time signature and key are edited in the
top bar only (SongReadout.qml), never twice. Then the song's other fields as the kit's InspectorRow calling this
object as its "bridge": behind More the rest (the song's Length is the picker beside them, below). The arrangement header (SongReadout.qml) is the quick way to the tempo, time signature
and key playing at the playhead, through the slots below. The picture to work to lives in the Picture corner (+ Add).

The rows come from the `doc.set` field operation (rule of individuality as data: a new song field shows up here by
itself). Every edit is that operation on the song (one undo step; a drag on a number is one gesture), the key is
`key.set` / `key.add` (song_edit.key_call), all through the screen's bridge so they join its one history.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core import RostrumError
from rostrum_gui import rows
from rostrum_gui.edits import Scrub, edit_label
from rostrum_gui.model import RowsModel
from rostrum_sound import main_mix

from rostrum_sound.doc import meter, tempo

from . import music_map, song_edit, timeline, timing

ELSEWHERE = ("tempo", "beatsPerBar", "beatUnit", "picture", "length")   # SongList's Bar 1 rows / the Picture corner / the Length picker (below): never rows here
LENGTHS = (4, 8, 16, 32, 64, 128)                    # the bars the Length picker offers, after "Until the last sound"
METERS = ["2/4", "3/4", "4/4", "5/4", "6/4", "7/4", "3/8", "5/8", "6/8", "7/8", "9/8", "12/8", "2/2"]


class SongPanel(QObject):
    changed = Signal()
    mainMixChanged = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge, self.doc = bridge, bridge.doc
        op = self.doc.kind.registry.field_op("doc")
        params = [p for p in op.params if p.name not in ELSEWHERE]
        self._layout = [r for r in rows.layout(SimpleNamespace(params=params)) if r["row"] != "group"]
        self._rows = RowsModel(rows.ROLES, self)
        self._more, self._scrub = False, None
        self._refresh()
        self._read_main()
        for sig in (bridge.docChanged, bridge.docStepped):     # the rows follow a drag live
            sig.connect(self._follow)
        bridge.mainMixChanged.connect(self._read_main)

    @property
    def _root(self) -> str:
        return self.doc.data["id"]

    # ---- reads -----------------------------------------------------------------------------------------------
    @Property(QObject, constant=True)
    def rows(self):
        return self._rows

    @Property(bool, notify=changed)
    def moreOpen(self):
        return self._more

    @Property(str, constant=True)
    def noKey(self):
        """The words for a song with no key (the panel's field, the header strip)."""
        return song_edit.NO_KEY

    @Property("QVariantList", constant=True)
    def meters(self):
        """The time signatures the pickers offer ("6/8"); the inspector of a change takes any."""
        return METERS

    @Property("QVariantList", constant=True)
    def tonics(self):
        return song_edit.TONICS

    @Property(str, notify=mainMixChanged)
    def mainMix(self):
        """"main" (this song is the project's main mix: the panel marks it), "other" (the panel offers "Make this the
        main mix") or "" (the song is not in a project folder yet). Read from the project once, and again when the
        mark moves: reading project.json and every item on each edit cost ~50 ms a binding (S59)."""
        return self._main

    def _read_main(self):
        f = self.doc.folder
        try:
            self._main = "" if not f else "main" if main_mix.is_main(f, self.doc.item_id) else "other"
        except RostrumError as e:          # a mark naming a gone item: said loudly; the panel offers to mark this one
            self._main = "other"
            self.bridge._fail(str(e))
        self.mainMixChanged.emit()

    # ---- the Length picker: "Until the last sound", or a number of bars --------------------------------------------
    def _bars(self) -> float | None:
        root = self.doc.data
        if root.get("length") is None:
            return None
        return round(meter.bar_at(root, tempo.beat_at(root, timing.sec(root["length"], root))), 2)

    @Property("QVariantList", notify=changed)
    def lengthChoices(self):
        """[{value, label}]: "" is until the last sound; a song whose length is not one of the list (a script set it)
        keeps its own entry, so the field always says what it is."""
        bars = self._bars()
        counts = sorted({*LENGTHS, *([bars] if bars is not None else [])})
        return [{"value": "", "label": "Until the last sound"},
                *({"value": f"{n:g}", "label": f"{n:g} bar" + ("" if n == 1 else "s")} for n in counts)]

    @Property(str, notify=changed)
    def lengthChoice(self):
        bars = self._bars()
        return "" if bars is None else f"{bars:g}"

    @Slot(str)
    def setLength(self, value):
        """"" puts the length back to the last sound; else that many bars (written in beats: it follows the tempo)."""
        root = self.doc.data
        end = None if value == "" else {"beat": meter.bar_start(root, int(float(value)) + 1)}
        b = self.bridge
        b._guard(lambda: b._apply([b.edit_call(self._root, "length", end)], "Song length"))

    @Slot()
    def makeMain(self):
        self.bridge.makeMainMix()

    # ---- what an InspectorRow calls on its bridge -----------------------------------------------------------
    @Slot(str, "QVariant", result=bool)
    def setValue(self, param, value):
        b = self.bridge
        return b._guard(lambda: b._apply([b.edit_call(self._root, param, value)],
                                         edit_label(self.doc, self._root, param, value)))

    @Slot(str)
    def beginScrub(self, param):
        self.endScrub()

        def go():
            self._scrub = Scrub(self.doc, self.bridge.who, self._root, param, self.bridge.edit_call)
        self.bridge._guard(go)

    @Slot(str, "QVariant")
    def scrub(self, param, value):
        if self._scrub is None or self._scrub.name != param:
            self.beginScrub(param)
        if self._scrub is not None:
            self.bridge._guard(lambda: self._scrub.preview(value))

    @Slot()
    def endScrub(self):
        s, self._scrub = self._scrub, None
        if s is not None:
            self.bridge._guard(lambda: self.bridge._done(s.end(False), ""))

    @Slot()
    def toggleMore(self):
        self._more = not self._more
        self._refresh()

    def _meter_here(self, target: str = "") -> str:
        """The time signature to edit: `target` (a change's id), else the one playing at the playhead (the song's own
        before the first change) -- the header and the panel edit what plays, like the tempo."""
        if target:
            return target
        t = self.bridge._t
        change = next((c for c in reversed(music_map.meter_marks(self.doc.data)) if 1e-9 < c["t"] <= t + 1e-6), None)
        return change["id"] if change else self._root

    @Slot(result=str)
    def meterHere(self):
        """The time signature playing at the playhead, "6/8" (the header's readout)."""
        item = self.doc.item(self._meter_here())
        return f'{item.get("beatsPerBar", 4)}/{item.get("beatUnit", 4)}'

    @Slot(str)
    @Slot(str, str)
    def setMeter(self, text, target=""):
        """A time signature, "6/8": beats in a bar and the beat unit together, one undo step -- on `target` (a
        change's id) or what plays at the playhead."""
        b, (per, unit) = self.bridge, (int(x) for x in text.split("/"))
        item = self._meter_here(target)
        b._guard(lambda: b._apply([b.edit_call(item, "beatsPerBar", per), b.edit_call(item, "beatUnit", unit)],
                                  f"Time signature {per}/{unit}"))

    @Slot(str, str)
    def setKey(self, tonic, mode):
        """The key playing at the playhead (none yet: a first key at the start)."""
        b = self.bridge
        b._guard(lambda: b._apply([song_edit.key_call(self.doc.data, b._t, tonic, mode, False)], "Set key"))

    # ---- the header's tempo: the tempo playing at the playhead (the song's own, or the change in force there) ---
    def _tempo_here(self) -> tuple[str, str]:
        t, root = self.bridge._t, self.doc.data
        change = next((c for c in reversed(music_map.tempo_marks(root)) if c["t"] <= t + 1e-6 and c["t"] > 1e-9), None)
        return (change["id"], "bpm") if change else (self._root, "tempo")

    @Slot(float)
    def setTempo(self, bpm):
        b, (target, param) = self.bridge, self._tempo_here()
        b._guard(lambda: b._apply([b.edit_call(target, param, bpm)], "Set tempo"))

    @Slot()
    def beginTempo(self):
        self.endScrub()
        target, param = self._tempo_here()

        def go():
            self._scrub = Scrub(self.doc, self.bridge.who, target, param, self.bridge.edit_call)
        self.bridge._guard(go)

    @Slot(float)
    def scrubTempo(self, bpm):
        if self._scrub is None:
            self.beginTempo()
        if self._scrub is not None:
            self.bridge._guard(lambda: self._scrub.preview(bpm))

    def toggleAnimate(self, _param):      # the song's fields have no keys (rows never show the mark here)
        pass

    # ---- inside ------------------------------------------------------------------------------------------------
    def _follow(self):
        """A change or a drag's step: the rows only when one of the song's own settings changed. Its rows read only
        those (its facts are none; times read the tempo and meter, also its own): a note drawn or a fader moved
        leaves them equal (compared by value: a change may copy the song's small lists, the markers, the tempos …)."""
        if {k: v for k, v in self.doc.data.items() if k not in timeline.OWN} != self._own:
            self._refresh()

    def _refresh(self):
        root = self.doc.data
        self._own = {k: v for k, v in root.items() if k not in timeline.OWN}
        evaluated = rows.evaluate(self._layout, self.bridge.shown_values(root), self.doc.kind.facts(root, self.doc),
                                  self._more)
        self._rows.update(evaluated) if self._rows.rows else self._rows.reset(evaluated)
        self.changed.emit()
