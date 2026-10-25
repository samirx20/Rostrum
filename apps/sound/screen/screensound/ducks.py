"""Ducks (sidechain dips) on the Mix page: a track dips while other tracks sound. Exposed to QML as `mixer.ducks`.

The strip lists a track's ducks as chips ("under melody"); a chip opens that duck's panel: which tracks it is under
(add / take away) and its settings, built from `duck.set`'s own params (valid_when / importance), `under` aside
(a list of tracks has its own chips). Every change is `duck.add` / `duck.set` / `duck.remove`; a drag on a number is
one gesture = one undo step. The panel belongs to the track's selection: picking anything else closes it.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_gui import rows
from rostrum_gui.edits import Scrub, edit_label, field_call
from rostrum_gui.model import RowsModel

OP = "duck.set"


def strip_ducks(track: dict, tracks: list[dict], label) -> dict:
    """What a track's strip shows: its ducks as chips, and the tracks a new duck could sit under."""
    names = {t["id"]: label(t) for t in tracks}
    chips = [{"id": d["id"], "label": "Dips under " + ", ".join(names.get(u, u) for u in d["under"])} for d in track.get("ducks", [])]
    return {"ducks": chips, "duckTargets": [{"id": t["id"], "name": label(t)} for t in tracks if t["id"] != track["id"]]}


class DuckHub(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge, self.doc = bridge, bridge.doc
        self._duck, self._more, self._scrub = "", False, None
        self._rows = RowsModel(rows.ROLES, self)
        self._static = [r for r in rows.layout(self.doc.kind.registry.field_op("duck")) if r["row"] != "group" and r["id"] != "under"]
        self._panel: dict = {}
        for sig in (bridge.docChanged, bridge.docStepped):     # the duck's rows follow a drag live
            sig.connect(self._refresh)
        bridge.selectedItemsChanged.connect(self._follow)

    @Property(QObject, constant=True)
    def controls(self):
        return self._rows

    @Property("QVariantMap", notify=changed)
    def panel(self):
        """{id, track, trackName, under: [{id, label}], addable: [{id, label}]}, or {} while no duck is open."""
        return self._panel

    @Property(bool, notify=changed)
    def moreOpen(self):
        return self._more

    # ---- edits: each one operation ------------------------------------------------------------------------------
    @Slot(str, str, result=bool)
    def add(self, track_id, under_id):
        """duck.add: this track dips under that one (one change); the new duck opens."""
        if not self._call({"op": "duck.add", "target": [track_id], "args": {"under": [under_id]}}, "Dip under another track"):
            return False
        self.select(self.doc.item(track_id)["ducks"][-1]["id"])
        return True

    @Slot(result=bool)
    def remove(self):
        duck = self._duck
        if not duck:
            return False
        self.close()
        return self._call({"op": "duck.remove", "target": [duck]}, "Stop dipping")

    @Slot(str, result=bool)
    def addUnder(self, track_id):
        return self._set_under([*self._item()["under"], track_id], "Dip under another track")

    @Slot(str, result=bool)
    def removeUnder(self, track_id):
        return self._set_under([u for u in self._item()["under"] if u != track_id], "Dip under fewer tracks")

    @Slot(str, "QVariant", result=bool)
    def setValue(self, param, value):
        return self._call(field_call(self.doc, self._duck, param, value), edit_label(self.doc, self._duck, param, value))

    @Slot(str)
    def beginScrub(self, param):
        self.endScrub()
        self.bridge._guard(lambda: setattr(self, "_scrub", Scrub(self.doc, self.bridge.who, self._duck, param)))

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

    # ---- what is open ------------------------------------------------------------------------------------------
    @Slot(str)
    def select(self, duck_id):
        """Open a duck's panel (with its track selected, so the Mix page shows one thing at a time)."""
        track = self.doc.parent_of(duck_id)[0]
        self.bridge.select(track)
        self._duck, self._more = duck_id, False
        self._refresh()

    @Slot()
    def close(self):
        self._duck = ""
        self._refresh()

    @Slot()
    def toggleMore(self):
        self._more = not self._more
        self._refresh()

    # ---- inside ------------------------------------------------------------------------------------------------
    def _item(self):
        return self.doc.item(self._duck)

    def _set_under(self, under, label):
        return self._call({"op": OP, "target": [self._duck], "args": {"under": under}}, label)

    def _call(self, call, label):
        return self.bridge._guard(lambda: self.bridge._apply([call], label))

    def _follow(self):
        if self._duck and self.bridge.selected != self.doc.parent_of(self._duck)[0]:
            self.close()

    def _refresh(self):
        if self._duck and not self.doc.has(self._duck):
            self._duck = ""
        if not self._duck:                  # none open: news only when one was (every edit and drag step comes here)
            if self._panel or self._rows.rows:
                self._panel = {}
                self._rows.reset([])
                self.changed.emit()
            return
        d = self._item()
        track = self.doc.parent_of(self._duck)[0]
        names = {t["id"]: self.bridge.label_of(t) for t in self.doc.data.get("tracks", [])}   # (never every note)
        self._panel = {"id": self._duck, "track": track, "trackName": names[track],
                       "under": [{"id": u, "label": names.get(u, u)} for u in d["under"]],
                       "addable": [{"id": i, "label": n} for i, n in names.items() if i != track and i not in d["under"]]}
        evaluated = rows.evaluate(self._static, d, self.doc.kind.facts(d, self.doc), self._more)
        self._rows.update(evaluated) if self._rows.rows else self._rows.reset(evaluated)
        self.changed.emit()
