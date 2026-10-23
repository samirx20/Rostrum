"""The stretch picked in the timeline (SPEC §9.2-9.3): the time between two keys of one setting, clicked on a layer's
line. Its layer is the selection; the settings panel shows the animation (AnimPanel.qml) until Esc, ‹ or another
pick. Screen state only; what it reads comes from rostrum2d.anims (anim.list's one source), every change is ONE
operation call (anim.ease, key.set, key.handles, key.remove). Offered to QML as `backend.stretch`.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d import fields as F
from rostrum2d.names import display_name
from rostrum2d.anims import PRESET_LABELS, PRESETS, animations
from rostrum_core.keys import ease as ease_at, springs
from rostrum_gui.edits import Drag

from . import eases


class StretchSelect(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._owner, self._ids, self._own, self._drag = bridge, "", [], False, None
        bridge.selectionChanged.connect(self._followed)
        bridge.docChanged.connect(self.changed)

    # ---- what is picked -----------------------------------------------------------------------------------------
    def _found(self):
        """(animation, stretch) picked now, from anims.animations of the placed layer (composition seconds); None if gone."""
        if not self._ids or not self.b.doc.has(self._owner):
            return None
        for a in animations(self.b.placed_item(self._owner)):
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
        """What the panel shows: names, From → to rows, Start, Length (composition seconds), the ease and its curve."""
        f = self._found()
        if not f:
            return {}
        a, s = f
        owner = self.b.doc.item(self._owner)
        key = self.b.placed_item(s["ids"][0])
        ease = key.get("ease", "smooth")
        rows = [{"prop": p, "from": s["from"][p], "to": s["to"][p], **_kind(F.param(owner["type"], p), p)} for p in a["props"]]
        return {"owner": self._owner, "ownerLabel": display_name(owner), "word": a["word"], "label": a["label"],
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
            self.b._keys.clear()
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
        if self._ids and not self._own and self.b.selected_layers() != [self._owner]:
            self.clear()

    # ---- one change each ----------------------------------------------------------------------------------------
    def _apply(self, calls, label) -> bool:
        return bool(calls) and self.b.guard(lambda: self.b.done(self.b.doc.apply(calls, self.b.who, label=label), ""))

    @Slot(str, result=bool)
    def setEase(self, preset):
        f = self._found()
        if not f or preset not in PRESETS:
            return False
        return self._apply([{"op": "anim.ease", "target": f[1]["ids"], "args": {"preset": preset}}], f"Ease: {PRESET_LABELS[preset]}")

    def _moves(self, keys, by):
        return [{"op": "key.set", "target": [k], "args": {"t": round(self.b.own_t(self._owner, self.b.placed_item(k)["t"] + by), 6)}}
                for k in keys]

    @Slot(float, result=bool)
    def setStart(self, t):
        """Both keys move together (the later ones first, so they never land on each other)."""
        f = self._found()
        if not f:
            return False
        by = round(t * self.b.comp()["fps"]) / self.b.comp()["fps"] - f[1]["start"]
        a, b = self._moves(f[1]["ids"], by), self._moves(f[1]["endIds"], by)
        return abs(by) > 1e-9 and self._apply(b + a if by > 0 else a + b, "Animation start")

    @Slot(float, result=bool)
    def setLength(self, length):
        """The end key moves; the start stays."""
        f = self._found()
        if not f or length <= 0:
            return False
        return self._apply(self._moves(f[1]["endIds"], length - f[1]["length"]), "Animation length")

    @Slot(str, str, float, result=bool)
    def setValue(self, prop, end, v):
        """From (end "from") or to ("to") of one number: its key there gets the value (key.set v)."""
        f = self._found()
        ids = (f[1]["ids"] if end == "from" else f[1]["endIds"]) if f else []
        mine = [k for k in ids if self.b.doc.item(k)["prop"] == prop]
        return bool(mine) and self._apply([{"op": "key.set", "target": mine, "args": {"v": v}}], f"Animation {end}")

    @Slot(result=bool)
    def reverse(self):
        """From and to swap (each key keeps its time and ease)."""
        f = self._found()
        if not f:
            return False
        s = f[1]
        calls = [{"op": "key.set", "target": [k], "args": {"v": (s["to"] if k in s["ids"] else s["from"])[self.b.doc.item(k)["prop"]]}}
                 for k in [*s["ids"], *s["endIds"]] if "v" in self.b.doc.item(k)]
        return self._apply(calls, "Reverse animation")

    @Slot(result=bool)
    def remove(self):
        """Delete: the stretch's keys no other stretch uses go; a stretch between two others becomes a Hold. One change."""
        f = self._found()
        if not f:
            return False
        a, s = f
        used = {k for t in a["stretches"] if t is not s for k in (*t["ids"], *t["endIds"])}
        gone = [k for k in (*s["ids"], *s["endIds"]) if k not in used]
        self._ids = []
        calls = [{"op": "key.remove", "target": gone, "args": {}}] if gone else \
            [{"op": "anim.ease", "target": s["ids"], "args": {"preset": "hold"}}]
        ok = self._apply(calls, "Delete animation")
        self.changed.emit()
        return ok

    # ---- the curve's handles: one change per drag (key.handles) ------------------------------------------------
    @Slot(str, result=bool)
    def begin(self, what):
        self.end()
        if not self._found():
            return False

        def go():
            self._drag = Drag(self.b.doc, self.b.who, "Spring" if what == "spring" else "Ease curve")
        return self.b.guard(go)

    @Slot(float, float, float, float)
    def curveTo(self, x1, y1, x2, y2):
        f = self._found()
        if self._drag is None or not f:
            return
        args = dict(x1=round(min(max(x1, 0), 1), 3), y1=round(min(max(y1, -2), 3), 3),
                    x2=round(min(max(x2, 0), 1), 3), y2=round(min(max(y2, -2), 3), 3))
        self.b.guard(lambda: self._drag.preview([{"op": "anim.ease", "target": f[1]["ids"], "args": args}]))

    @Slot(float, float)
    def springTo(self, bounce, speed):
        """A spring's Bounce or Speed, dragged or typed (one change per drag, begin … end)."""
        f = self._found()
        if self._drag is None or not f:
            return
        args = {"bounce": round(min(max(bounce, 0), 1), 3), "speed": round(min(max(speed, 0), 1), 3)}
        self.b.guard(lambda: self._drag.preview([{"op": "key.set", "target": f[1]["ids"], "args": args}]))

    @Slot()
    def end(self):
        d, self._drag = self._drag, None
        if d is not None:
            self.b.guard(lambda: self.b.done(d.end(), ""))


def _kind(param, prop) -> dict:
    """A From → to row's name and how its numbers show: the setting's unit and display kind ("0 % → 100 %", px, °)."""
    if param is None:
        return {"label": prop, "unit": "", "display": "", "step": 0.01}
    return {"label": param.label, "unit": param.unit if param.unit != "×" else "", "display": param.display,
            "step": param.step or 0.01}
