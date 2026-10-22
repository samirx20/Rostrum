"""The song in the settings panel, shown while nothing is selected (DESIGN.md decision 4; the Song popup that covered
the notes is gone): tempo, beats per bar, length, the key at the start, and behind More the rest of the song's own
fields (sample rate, picture). Exposed to QML as `songPanel`; SongSettings.qml draws it with the kit's InspectorRow,
which calls this object as its "bridge".

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

from . import song_edit

UP_FRONT = ("tempo", "beatsPerBar", "length")        # always in sight, whatever their importance in the field list
UNSET = -1                                           # the length row's value while the song has none: shown in words
UNSET_WORDS = {"length": "until the last sound"}


class SongPanel(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge, self.doc = bridge, bridge.doc
        op = self.doc.kind.registry.field_op("doc")
        params = [dataclasses.replace(p, importance="primary") if p.name in UP_FRONT else p for p in op.params]
        self._layout = [r for r in rows.layout(SimpleNamespace(params=params)) if r["row"] != "group"]
        self._rows = RowsModel(rows.ROLES, self)
        self._more, self._scrub = False, None
        self._refresh()
        bridge.docChanged.connect(self._refresh)

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

    @Property("QVariantMap", notify=changed)
    def key(self):
        """{tonic, mode, set}: the key at the start of the song (set false: the song has no key yet)."""
        st = song_edit.state(self.doc.data, None, 0.0)
        return {"tonic": st["tonic"] if st["hasKey"] else "", "mode": st["mode"], "set": st["hasKey"]}

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
        """The song's key at the start (a key change later in the song is made on the ruler or in the popover)."""
        b = self.bridge
        b._guard(lambda: b._apply([song_edit.key_call(self.doc.data, 0.0, tonic, mode, False)], "Set key"))

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
