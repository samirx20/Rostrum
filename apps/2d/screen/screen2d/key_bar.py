"""The key bar (UX_SPEC 3.18, INTERACTION 1.5 point 6): the settings panel's Key block (KeyPanel.qml) while keys are picked. Ease ▾, a small
curve to drag, for one key its Time and Value, and for a spring Bounce and Speed. Every picked key changes; each pick,
field edit or whole drag is ONE change (key.set, key.handles: the operations an agent calls). Offered to QML as
`backend.keyBar`. Screen state only; the keys picked are key_select.py's.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core.keys import after as last_key, ease as ease_at, keys_of, springs
from rostrum_gui.edits import Drag

from . import beat_words, eases


class KeyBar(QObject):
    changed = Signal()
    menuAsked = Signal(float, float)        # a key's right-click: the Ease list at this window point (LayerTimeline.qml)

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._drag, self._grab = bridge, None, None
        bridge._keys.changed.connect(self.changed)
        bridge.selectionChanged.connect(self.changed)
        bridge.outlineChanged.connect(self.changed)

    def picked(self) -> list[str]:
        """The keys it acts on: those picked in the timeline or the curve editor (key_select.py)."""
        return [k for k in self.b._keys.ids if self.b.doc.has(k)]

    def _first(self) -> dict:
        ids = self.picked()
        return self.b.placed_item(ids[0]) if ids else {}

    # ---- reads ------------------------------------------------------------------------------------------------
    @Property(bool, notify=changed)
    def shown(self):
        return bool(self.picked())

    @Property(int, notify=changed)
    def count(self):
        return len(self.picked())

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
        """The first key's ease as 25 points [x, y] (0..1, y may leave it): what the small curve draws."""
        k = self._first()
        return [[i / 24, ease_at(k, i / 24)] for i in range(25)] if k else []

    @Property(bool, notify=changed)
    def one(self):
        return len(self.picked()) == 1

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
        return self.one and "v" in self._first()

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

    @Slot(float, result=bool)
    def setTime(self, t):
        """One key's time (composition seconds), on a whole frame; another key of that setting there refuses."""
        if not self.one:
            return False
        fps, kid = self.b.comp()["fps"], self.picked()[0]
        own = self.b.own_t(self.b.doc.parent_of(kid)[0], round(t * fps) / fps)
        return self._apply(self._all({"t": round(own, 6)}), "Key time")

    @Slot(float, result=bool)
    def setValue(self, v):
        return self.hasValue and self._apply(self._all({"v": v}), "Key value")

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
