"""The song's own settings, exposed to QML as `songPanel`. Tempo, beats per bar and the key have ONE home: the
arrangement header (SongReadout.qml: click and type, drag the tempo), which edits what plays at the playhead through
the slots below. The settings panel, shown while nothing is selected (SongSettings.qml, the kit's InspectorRow calling
this object as its "bridge"), holds the rest: length, and behind More the other song fields. The picture to work to
lives in the Picture corner (+ Add), not here.

The rows come from the `doc.set` field operation (rule of individuality as data: a new song field shows up here by
itself). Every edit is that operation on the song (one undo step; a drag on a number is one gesture), the key is
`key.set` / `key.add` (song_edit.key_call), all through the screen's bridge so they join its one history.
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui import rows
from rostrum_gui.edits import Scrub, edit_label
from rostrum_gui.model import RowsModel
from rostrum_sound import main_mix

from . import music_map, song_edit

UP_FRONT = ("length",)                               # always in sight, whatever their importance in the field list
ELSEWHERE = ("tempo", "beatsPerBar", "picture")      # their home is the header / the Picture corner: never rows here
UNSET = -1                                           # the length row's value while the song has none: shown in words
UNSET_WORDS = {"length": "until the last sound"}


class SongPanel(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge, self.doc = bridge, bridge.doc
        op = self.doc.kind.registry.field_op("doc")
        params = [dataclasses.replace(p, importance="primary") if p.name in UP_FRONT else p
                  for p in op.params if p.name not in ELSEWHERE]
        self._layout = [r for r in rows.layout(SimpleNamespace(params=params)) if r["row"] != "group"]
        self._rows = RowsModel(rows.ROLES, self)
        self._more, self._scrub = False, None
        self._refresh()
        bridge.docChanged.connect(self._refresh)
        bridge.mainMixChanged.connect(self.changed)

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

    @Property(str, notify=changed)
    def mainMix(self):
        """"main" (this song is the project's main mix: the panel marks it), "other" (the panel offers "Make this the
        main mix") or "" (the song is not in a project folder yet)."""
        f = self.doc.folder
        return "" if not f else "main" if main_mix.is_main(f, self.doc.item_id) else "other"

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
    def _refresh(self):
        root = self.doc.data
        evaluated = rows.evaluate(self._layout, self.bridge.shown_values(root), self.doc.kind.facts(root, self.doc),
                                  self._more)
        for r in evaluated:      # a field left out ("until the last sound") says so in words, not as 0
            if r["row"] == "param" and r["id"] in UNSET_WORDS and root.get(r["id"]) is None:
                r["value"], r["words"] = UNSET, [{"value": UNSET, "label": UNSET_WORDS[r["id"]]}]
        self._rows.update(evaluated) if self._rows.rows else self._rows.reset(evaluated)
        self.changed.emit()
