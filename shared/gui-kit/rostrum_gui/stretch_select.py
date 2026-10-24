"""The stretch picked in the timeline (2D SPEC §9.2-9.3, 3D SPEC §9), in every app with keys: the time between two
keys of one setting, clicked on an item's line. Its item is the selection; the settings panel shows the animation
(AnimPanel.qml) until Esc, ‹ or another pick. Screen state only; what it reads comes from rostrum_core.keys.animations
(anim.list's one source), every change is ONE operation call (anim.ease, key.set, key.remove). Offered to QML as
`backend.stretch`.

What differs per app is a small subclass (2D: screen2d/stretch_select.py; 3D: screen3d/stretch3d.py):
`animations(owner_id)` (in the app's names and time), `key(id)` (a key as placed in that time), `own_t(owner_id, t)`
(a time back in the owner's own seconds), `fps()`, `owner_label(item)`, `param(type, prop)`, `picked_items()` (the
items selected now) and `let_keys_go()` (picked keys let go when a stretch is picked).
The changes themselves (ease, start, length, values, reverse, delete, curve handles) are in stretch_edits.py.
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from rostrum_core.keys import ease as ease_at, springs
from rostrum_core.keys.anims import PRESET_LABELS, PRESETS

from . import eases
from .stretch_edits import StretchEdits


class StretchSelect(StretchEdits):
    changed = Signal()

    # ---- the app's part (override) ------------------------------------------------------------------------------
    def animations(self, owner_id: str) -> list[dict]:
        raise NotImplementedError

    def key(self, key_id: str) -> dict:
        return self.b.doc.item(key_id)

    def own_t(self, owner_id: str, t: float) -> float:
        return t

    def fps(self) -> float:
        raise NotImplementedError

    def owner_label(self, item: dict) -> str:
        return str(item.get("name") or item["id"])

    def param(self, type_: str, prop: str):
        return None

    def picked_items(self) -> list[str]:
        return list(self.b.selection)

    def let_keys_go(self):
        pass

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._owner, self._ids, self._own, self._drag = bridge, "", [], False, None
        bridge.selectedItemsChanged.connect(self._followed)
        for sig in (bridge.docChanged, bridge.docStepped):     # the curve follows its handle's drag live
            sig.connect(self.changed)

    # ---- what is picked -----------------------------------------------------------------------------------------
    def _found(self):
        """(animation, stretch) picked now, from the app's animations of the item; None if gone."""
        if not self._ids or not self.b.doc.has(self._owner):
            return None
        for a in self.animations(self._owner):
            for s in a["stretches"]:
                if set(s["ids"]) & set(self._ids):
                    return a, s
        return None

    @Property(bool, notify=changed)
    def shown(self):
        return self._found() is not None

    @Property("QVariantList", notify=changed)
    def ids(self):
        """Every key of the picked stretch (its start and end keys): the timeline draws them blue."""
        f = self._found()
        return [*f[1]["ids"], *f[1]["endIds"]] if f else []

    @Property("QVariantMap", notify=changed)
    def info(self):
        """What the panel shows: names, From → to rows, Start, Length (seconds), the ease and its curve."""
        f = self._found()
        if not f:
            return {}
        a, s = f
        owner = self.b.doc.item(self._owner)
        key = self.key(s["ids"][0])
        ease = key.get("ease", "smooth")
        rows = [{"prop": p, "from": s["from"][p], "to": s["to"][p], **_kind(self.param(owner["type"], p), p)} for p in a["props"]]
        return {"owner": self._owner, "ownerLabel": self.owner_label(owner), "word": a["word"], "label": a["label"],
                "rows": rows, "start": s["start"], "length": s["length"], "preset": s["preset"], "ease": ease,
                "easeLabel": PRESET_LABELS.get(s["preset"], eases.label_of(ease)),
                "handles": eases.handles(key) if ease in ("linear", "custom", *eases.BEZIERS) else [],
                "feel": list(springs.feel_of(key)) if ease == "spring" else [],      # [bounce, speed] (H41's key fields)
                "curve": [[i / 24, ease_at(key, i / 24)] for i in range(25)]}

    @Property("QVariantList", notify=changed)
    def curve(self):
        return self.info.get("curve", [])

    @Property("QVariantList", notify=changed)
    def handles(self):
        return self.info.get("handles", [])

    @Property("QVariantList", constant=True)
    def presets(self):
        return [{"value": v, "label": PRESET_LABELS[v]} for v in PRESETS]

    # ---- picking ------------------------------------------------------------------------------------------------
    @Slot(str, "QVariantList")
    def pick(self, owner, ids):
        """A click on a stretch: its layer becomes the selection (alone), picked keys let go, the stretch is shown."""
        self._own = True
        try:
            self.let_keys_go()
            self.b.select(owner)
        finally:
            self._own = False
        self._owner, self._ids = owner, [str(i) for i in ids]
        self.changed.emit()

    @Slot()
    def clear(self):
        if self._ids:
            self._owner, self._ids = "", []
            self.changed.emit()

    def _followed(self):
        if self._ids and not self._own and self.picked_items() != [self._owner]:
            self.clear()


def _kind(param, prop) -> dict:
    """A From → to row's name and how its numbers show: the setting's unit and display kind ("0 % → 100 %", px, °)."""
    if param is None:
        return {"label": prop, "unit": "", "display": "", "step": 0.01}
    return {"label": param.label, "unit": param.unit if param.unit != "×" else "", "display": param.display,
            "step": param.step or 0.01}
