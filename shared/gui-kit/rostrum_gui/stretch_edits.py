"""The stretch's changes (ease, start, length, values, reverse, delete, the curve's handles): the editing half of
StretchSelect (stretch_select.py). Each is ONE operation call, one history step; a handle's drag is one step from
`begin` to `end`. Reads the picked stretch through `self._found()` and the app's parts of StretchSelect."""
from __future__ import annotations

from PySide6.QtCore import QObject, Slot
from rostrum_core.keys.easing import EASE_LIST, OLD_NAMES

from . import eases
from .edits import Drag


class StretchEdits(QObject):
    # needs from StretchSelect: self.b (the bridge), self._owner, self._ids, self._drag, _found(), key(), own_t(), fps(), changed

    # ---- one change each ----------------------------------------------------------------------------------------
    def _apply(self, calls, label) -> bool:
        return bool(calls) and self.b._guard(lambda: self.b._done(self.b.doc.apply(calls, self.b.who, label=label), ""))

    @Slot(str, result=bool)
    def setEase(self, ease):
        """An ease of the one list (its id, as key.set {ease} takes it; "in" / "out" still read): anim.ease, one change."""
        f = self._found()
        if not f or not any(e["id"] == OLD_NAMES.get(ease, ease) for e in EASE_LIST):
            return False
        return self._apply([{"op": "anim.ease", "target": f[1]["ids"], "args": {"preset": ease}}], f"Ease: {eases.label_of(ease)}")

    @Slot(str)
    def preview(self, ease):
        """The pointer on an ease in the list: the app plays it on the stretch, nothing kept; "" puts it back."""
        f = self._found()
        self.preview_ease(f[1]["ids"] if f else [], ease)

    def _moves(self, keys, by):
        return [{"op": "key.set", "target": [k], "args": {"t": round(self.own_t(self._owner, self.key(k)["t"] + by), 6)}}
                for k in keys]

    @Slot(float, result=bool)
    def setStart(self, t):
        """Both keys move together (the later ones first, so they never land on each other)."""
        f = self._found()
        if not f:
            return False
        by = round(t * self.fps()) / self.fps() - f[1]["start"]
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
        return self.b._guard(go)

    @Slot(float, float, float, float)
    def curveTo(self, x1, y1, x2, y2):
        f = self._found()
        if self._drag is None or not f:
            return
        args = dict(x1=round(min(max(x1, 0), 1), 3), y1=round(min(max(y1, -2), 3), 3),
                    x2=round(min(max(x2, 0), 1), 3), y2=round(min(max(y2, -2), 3), 3))
        self.b._guard(lambda: self._drag.preview([{"op": "anim.ease", "target": f[1]["ids"], "args": args}]))

    @Slot(float, float)
    def springTo(self, bounce, speed):
        """A spring's Bounce or Speed, dragged or typed (one change per drag, begin … end)."""
        f = self._found()
        if self._drag is None or not f:
            return
        args = {"bounce": round(min(max(bounce, 0), 1), 3), "speed": round(min(max(speed, 0), 1), 3)}
        self.b._guard(lambda: self._drag.preview([{"op": "key.set", "target": f[1]["ids"], "args": args}]))

    @Slot()
    def end(self):
        d, self._drag = self._drag, None
        if d is not None:
            self.b._guard(lambda: self.b._done(d.end(), ""))
