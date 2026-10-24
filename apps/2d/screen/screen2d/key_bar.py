"""The key bar (UX_SPEC 3.18, INTERACTION 1.5 point 6): the settings panel's Key block (KeyPanel.qml) while keys are picked. Ease ▾, a small
curve to drag, for one key its Time and Value, and for a spring Bounce and Speed. Every picked key changes; each pick,
field edit or whole drag is ONE change (key.set, key.handles: the operations an agent calls). Offered to QML as
`backend.keyBar`. Screen state only; the keys picked are key_select.py's.
"""
from __future__ import annotations

from rostrum_gui import news

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core.keys import after as last_key, ease as ease_at, keys_of, springs
from rostrum_gui.edits import Drag

from rostrum2d import fields as F

from . import beat_words, eases


class KeyBar(QObject):
    changed = Signal()
    menuAsked = Signal(float, float)        # a key's right-click: the Ease list at this window point (LayerTimeline.qml)

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._drag, self._grab = bridge, None, None
        told = news.relay(self)                             # only news (the bar redid itself on every edit)
        bridge._keys.changed.connect(told)
        bridge.selectedItemsChanged.connect(told)
        bridge.outlineChanged.connect(told)

    def picked(self) -> list[str]:
        """The keys it acts on: those picked in the timeline or the curve editor (key_select.py)."""
        ids = self.b._keys.ids
        if not isinstance(ids, list):       # the screen is closing: the bridge's key list is already gone (the property object, not a list)
            return []
        return [k for k in ids if self.b.doc.has(k) and "prop" in self.b.doc.item(k)]    # keys only, never a layer id

    def _first(self) -> dict:
        ids = self.picked()
        return self.b.placed_item(ids[0]) if ids else {}

    # ---- reads ------------------------------------------------------------------------------------------------
    @Property(bool, notify=changed)
    def shown(self):
        return bool(self.picked())

    def _moments(self) -> set:
        """(layer, time) of the picked keys: a Position key is its X and Y keys at one time, ONE key on screen."""
        return {(self.b.doc.parent_of(k)[0], round(self.b.doc.item(k)["t"], 6)) for k in self.picked()
                if isinstance(self.b.doc.item(k).get("t"), (int, float))}

    @Property(int, notify=changed)
    def count(self):
        """How many keys the panel says ("Key" / "3 keys"): moments of a layer, the halves of a pair counted once."""
        return len(self._moments()) or len(self.picked())

    @Property(str, notify=changed)
    def ease(self):
        """The first key's ease ("" when the picked keys differ: the field then reads Mixed)."""
        ids = self.picked()
        found = {self.b.doc.item(i).get("ease", "smooth") for i in ids}
        return found.pop() if len(found) == 1 else ""

    @Property("QVariantList", constant=True)
    def eases(self):
        return [{"value": e["value"], "label": e["label"]} for e in eases.EASES]

    @Property("QVariantList", notify=changed)
    def options(self):
        """The Ease ▾ list, plus the key's own ease when it is one of the document's others (Snappy …) or Mixed."""
        out, now = self.eases, self.ease
        if not now:
            return [{"value": "", "label": "Mixed"}, *out]
        return out if any(e["value"] == now for e in out) else [{"value": now, "label": eases.label_of(now)}, *out]

    @Property("QVariantList", notify=changed)
    def handles(self):
        """[x1, y1, x2, y2] of the small curve; [] where the curve is not a cubic (spring, jump, bounce)."""
        k = self._first()
        return eases.handles(k) if k and k.get("ease", "smooth") in ("linear", "custom", *eases.BEZIERS) else []

    @Property("QVariantList", notify=changed)
    def curve(self):
        """The first key's ease as 61 points [x, y] (0..1, y may leave it: a spring's wobbles show): what the small curve draws."""
        k = self._first()
        return [[i / 60, ease_at(k, i / 60)] for i in range(61)] if k else []

    @Property(bool, notify=changed)
    def one(self):
        """One key on screen (one key, or a pair's two at one time): its Time shows."""
        return len(self.picked()) == 1 or (bool(self.picked()) and len(self._moments()) == 1)

    @Property(float, notify=changed)
    def time(self):
        return float(self._first().get("t", 0.0))

    @Property(str, notify=changed)
    def beat(self):
        """One key on a beat of the music: "bar 5 beat 3" beside its Time ("" otherwise; beat_words.py)."""
        k = self._first()
        return beat_words.say(self.b, k["t"]) if self.one and isinstance(k.get("t"), (int, float)) else ""

    @Property(bool, notify=changed)
    def hasValue(self):
        return len(self.picked()) == 1 and "v" in self._first()

    @Property("QVariantMap", notify=changed)
    def valueField(self):
        """How the one key's Value shows: its setting's own step, unit and display ("1039 px", not "1039.32")."""
        ids = self.picked()
        p = F.param(self.b.doc.item(self.b.doc.parent_of(ids[0])[0])["type"], self.b.doc.item(ids[0])["prop"]) if ids else None
        return {"step": p.step or 0.01, "unit": p.unit, "display": p.display} if p else {"step": 0.01, "unit": "", "display": ""}

    @Property(float, notify=changed)
    def value(self):
        return float(self._first().get("v", 0.0))

    @Property("QVariantList", notify=changed)
    def feel(self):
        """[bounce, speed] of the first key's spring."""
        return list(springs.feel_of(self._first())) if self.ease == "spring" else []

    @Slot(float, float)
    def askMenu(self, x, y):
        self.menuAsked.emit(x, y)

    # ---- one change each --------------------------------------------------------------------------------------
    def _all(self, args: dict) -> list[dict]:
        return [{"op": "key.set", "target": self.picked(), "args": args}]

    def _apply(self, calls, label):
        return self.b.guard(lambda: self.b.done(self.b.doc.apply(calls, self.b.who, label=label), ""))

    @Slot(str, result=bool)
    def setEase(self, value):
        """Ease ▾ or a key's right-click or F9 …: every picked key. Custom starts from the curve shown now."""
        if not self.picked() or not value:
            return False
        n = len(self.picked())
        label = f"Ease {n} keys: {eases.label_of(value)}" if n > 1 else f"Ease: {eases.label_of(value)}"
        if value == "custom":
            x1, y1, x2, y2 = eases.handles(self._first())
            return self._apply([{"op": "key.handles", "target": self.picked(), "args": dict(x1=x1, y1=y1, x2=x2, y2=y2)}], label)
        words = dict(zip(("bounce", "speed"), springs.feel_of(self._first()))) if value == "spring" else {}
        return self._apply(self._all({"ease": value, **words}), label) and self._played()   # a spring in words (spring.py)

    def _played(self) -> bool:
        self.b._ease_play.play(self.picked())         # the stretch plays once on the canvas (ease_play.py)
        return True

    # ---- the ⋯ menu: After the last key (UX_SPEC 3.18), for the picked keys that are their field's last ---------
    def _lasts(self) -> list[str]:
        out = []
        for kid in self.picked():
            key = self.b.doc.item(kid)
            row = keys_of(self.b.placed_item(self.b.doc.parent_of(kid)[0]), key["prop"])
            if len(row) > 1 and row[-1]["id"] == kid:
                out.append(kid)
        return out

    @Property("QVariantList", notify=changed)
    def afters(self):
        """After the last key's choices, [] unless a picked key is its field's last (then the ⋯ menu shows them)."""
        return [{"value": a, "label": last_key.WORDS[a]} for a in last_key.AFTER] if self._lasts() else []

    @Property(str, notify=changed)
    def after(self):
        found = {self.b.doc.item(k).get("after", "stay") for k in self._lasts()}
        return found.pop() if len(found) == 1 else ""

    @Slot(str, result=bool)
    def setAfter(self, value):
        """key.set {after} on the picked last keys: one change."""
        lasts = self._lasts()
        if not lasts or value not in last_key.AFTER:
            return False
        return self._apply([{"op": "key.set", "target": lasts, "args": {"after": value}}], f"After the last key: {last_key.WORDS[value]}")

    @Slot(str)
    def hold(self, field):
        """A Key field's caret went in (Time, Value): what it commits goes to the keys picked now (the kit's rule)."""
        self.b.hold_ids(f"key.{field}", self.picked())

    @Slot(str)
    def release(self, field):
        held = self.b._kit.held
        if held and held[0] == f"key.{field}":
            self.b._kit.held = None

    def _typed_for(self, field):
        """The keys a typed Time / Value is for: those held when its typing started, else those picked now."""
        ids = [k for k in self.b.held_ids(f"key.{field}", self.picked()) if "prop" in self.b.doc.item(k)]
        if not ids:
            self.b._fail(f"Error: key {field}: the key it was typed for is gone; the value is dropped.",
                         "The typed value was dropped: the key it was typed for is gone.")
        return ids

    @Slot(float, result=bool)
    def setTime(self, t):
        """One key's time (composition seconds), on a whole frame; another key of that setting there refuses."""
        ids = self._typed_for("time")
        owners = {self.b.doc.parent_of(k)[0] for k in ids}
        if len(owners) != 1 or len({self.b.doc.item(k)["t"] for k in ids}) != 1:     # one key, or a pair's two at one time
            return False
        fps = self.b.comp()["fps"]
        own = self.b.own_t(owners.pop(), round(t * fps) / fps)
        return self._apply([{"op": "key.set", "target": ids, "args": {"t": round(own, 6)}}], "Key time")

    @Slot(float, result=bool)
    def setValue(self, v):
        ids = self._typed_for("value")
        return bool(ids) and self._apply([{"op": "key.set", "target": ids, "args": {"v": v}}], "Key value")

    # ---- drags: the small curve's handles and the spring sliders, one change per drag -------------------------
    @Slot(str, result=bool)
    def begin(self, what):
        """what: "curve" (a handle of the small curve) or "spring" (Bounce or Speed)."""
        self.end()
        if not self.picked():
            return False
        self._grab = what

        def go():
            self._drag = Drag(self.b.doc, self.b.who, "Ease curve" if what == "curve" else "Spring")
        return self.b.guard(go)

    @Slot(float, float, float, float)
    def curveTo(self, x1, y1, x2, y2):
        if self._drag is None or self._grab != "curve":
            return
        args = dict(x1=round(min(max(x1, 0), 1), 3), y1=round(min(max(y1, -2), 3), 3),
                    x2=round(min(max(x2, 0), 1), 3), y2=round(min(max(y2, -2), 3), 3))
        self.b.guard(lambda: self._drag.preview([{"op": "key.handles", "target": self.picked(), "args": args}]))

    @Slot(float, float)
    def springTo(self, bounce, speed):
        if self._drag is None or self._grab != "spring":
            return
        args = {"bounce": round(bounce, 3), "speed": round(speed, 3)}
        self.b.guard(lambda: self._drag.preview(self._all(args)))

    @Slot()
    def end(self):
        d, self._drag, self._grab = self._drag, None, None
        if d is not None:
            self.b.guard(lambda: self.b.done(d.end(), ""))
