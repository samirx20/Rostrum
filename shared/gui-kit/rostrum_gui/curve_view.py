"""The kit's curve view (the timeline's Curves, CurveEditor.qml): value curves over time, keys and their Bézier handles
to drag, and All curves. An app subclasses `CurveView` and answers the hooks below (2D: screen2d/curves.py, 3D:
screen3d/curves3d.py); everything else is here, once.

Which curves: the picked items' animated number fields (their parts' too); with nothing picked, or All curves chosen,
every animated item's. All curves is a choice only where it would show more. Every change is an operation: a key drag
is `key.set` {t, v}, a handle drag `key.set` {ease: custom, x1 y1 x2 y2} (a named cubic becomes custom from its own
numbers); each drag is one doc.gesture = one undo step. Tangent kinds (Smooth, Linear, Hold …) are the key's Ease list
(a right-click on a key: backend.keyBar). Times and values from QML are seconds and field values; a curve's value
range is frozen while a drag runs.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core.keys import keys_of
from rostrum_core.keys.curve import curve_of, handles_of

from . import news
from .curve_rows import entry, numbers
from .edits import Drag
from .per_state import PerState
from .time_snap import snap

X, Y = ("x1", "x2"), ("y1", "y2")


class CurveView(QObject):
    changed = Signal()

    # ---- the app's hooks --------------------------------------------------------------------------------------------
    def picked_items(self) -> list[dict]: raise NotImplementedError        # the selected items (owners of keys)
    def scene_items(self) -> list[dict]: raise NotImplementedError         # every item that may have keys, in list order
    def fields_of(self, item: dict) -> list[tuple[dict, str]]: raise NotImplementedError   # (owner, prop), its parts too
    def field_label(self, owner: dict, prop: str, item: dict) -> str: raise NotImplementedError
    def item_label(self, item: dict) -> str: raise NotImplementedError
    def limits(self, owner: dict, prop: str) -> tuple[float, float]: return -1e9, 1e9
    def picked_keys(self) -> list[str]: raise NotImplementedError
    def pick_key(self, key_id: str) -> None: raise NotImplementedError     # picked as a diamond click would
    def snap_targets(self, key_id: str) -> list: return []                 # rostrum_gui.time_snap Targets
    def time_limits(self) -> tuple[float, float, float]: raise NotImplementedError   # (first, last second, fps)
    def key_time(self, owner: dict, key: dict, t: float): return round(t, 6)        # key.set's `t` for seconds t
    def state(self) -> tuple: raise NotImplementedError   # (the data first, then the selection picked_items reads)
    def item(self, id_: str) -> dict: return self.b.doc.item(id_)
    def curve(self, owner: dict, prop: str) -> dict: return curve_of(owner, prop)
    def guard(self, fn): return self.b._guard(fn)                         # the kit DocBridge's
    def done(self, change): self.b._done(change, "")

    def __init__(self, bridge, news_signal, parent=None):
        super().__init__(parent)
        self.b, self._on, self._all, self._hidden, self._drag, self._grab, self._frozen = bridge, False, False, set(), None, None, {}
        self._kept = PerState()          # the curves, once per state (news.relay reads them, then QML: twice per step)
        self._facts = PerState()         # which items have curves, once per state()
        news_signal.connect(news.relay(self))

    def _groups(self, every: bool) -> list[tuple[dict, list]]:
        """[(item, [(owner, prop)])] of the animated items, the scene's or the picked ones; once per state."""
        def work():
            items = self.scene_items() if every else self.picked_items()
            return [(it, ns) for it in items if (ns := numbers(self, it))]
        return self._facts.read(self.state(), f"groups{every}", work)

    def _mine(self):
        return self._groups(False)

    @Property(bool, notify=changed)
    def offered(self):
        """Something in the scene is animated (a number): else the timeline's Keys | Curves switch is absent."""
        return bool(self._groups(True))

    @Property(bool, notify=changed)
    def on(self):
        """The curve view shows: Curves chosen and something to see (the choice is kept for when there is again)."""
        return self._on and self.offered

    @Property(bool, notify=changed)
    def canAll(self):
        """All curves would show more than the picked items' own: the choice is there only then."""
        mine = self._mine()
        return bool(mine) and len(mine) < len(self._groups(True))

    @Property(bool, notify=changed)
    def all(self):
        """Every animated item's curves show: chosen, or nothing picked has any."""
        return self._all or not self._mine()

    @Slot(bool)
    def setOn(self, on):
        self._on = on
        self.changed.emit()

    @Slot(bool)
    def setAll(self, every):
        self._all = every
        self.changed.emit()

    @Slot()
    def showAll(self):
        """The animation panel's All curves: the Curves view with every item's curves."""
        self._on, self._all = True, True
        self.changed.emit()

    @Slot(str)
    def toggleField(self, field_id):
        self._hidden ^= {field_id}
        self.changed.emit()

    @Slot(str)
    def toggleGroup(self, item_id):
        """An item's name in the legend: hide all its curves, or show them all when all were hidden."""
        ids = {f["id"] for f in self.fields if f["group"] == item_id}
        self._hidden = self._hidden - ids if ids <= self._hidden else self._hidden | ids
        self.changed.emit()

    @Property("QVariantList", notify=changed)
    def fields(self):
        """One entry per curve (curve_rows.entry). Empty while the view is off: nothing samples curves no one sees."""
        if not self.on:
            return []
        state = (*self.state(), tuple(self.picked_keys()), self.all, frozenset(self._hidden), tuple(sorted(self._frozen.items())))
        return self._kept.read(state, "fields", self._curves)

    def _curves(self):
        picked = (self.picked_keys() or [""])[0]
        out = []
        for item, ns in self._groups(self.all):
            out += [entry(self, len(out) + i, item, o, p, picked, self._frozen, self._hidden) for i, (o, p) in enumerate(ns)]
        return out

    # ---- drags: one gesture each --------------------------------------------------------------------------------
    def _begin(self, label, grab) -> bool:
        self.endDrag()
        self._frozen = {f["id"]: (f["lo"], f["hi"]) for f in self.fields}

        def go():
            self._drag, self._grab = Drag(self.b.doc, self.b.who, label), grab
        return bool(self.guard(go))

    def _owner(self, key: dict) -> dict:
        return self.item(self.b.doc.parent_of(key["id"])[0])

    @Slot(str, result=bool)
    def beginKeyDrag(self, key_id):
        self.pick_key(key_id)
        key = self.item(key_id)
        return self._begin("Move key", {"key": key_id, "found": self.snap_targets(key_id), "from": key["t"]})

    @Slot(float, float)
    @Slot(float, float, float)
    def keyTo(self, t, v, within=0.0):
        """The key's new time and value: key.set. Its time snaps within `within` seconds (0 = Ctrl held: free), else to a
        whole frame; it never takes another key's time on its field; its value stays in the field's range."""
        if self._drag is None or "which" in self._grab:
            return
        key = self.item(self._grab["key"])
        owner = self._owner(key)
        first, last, fps = self.time_limits()
        t, caught = snap(t, self._grab["found"], within, fps)
        t = min(max(t, first), last)
        if any(k["id"] != key["id"] and abs(k["t"] - t) < 1e-6 for k in keys_of(owner, key["prop"])):
            t, caught = key["t"], None
        self.b.timeSnap.show(t - self._grab["from"], fps, caught, t, owner["id"])
        lo, hi = self.limits(owner, key["prop"])
        args = {"t": self.key_time(owner, key, t), "v": round(min(max(v, lo), hi), 4)}
        self.guard(lambda: self._drag.preview([{"op": "key.set", "target": [key["id"]], "args": args}]))

    @Slot(str, int, result=bool)
    def beginHandleDrag(self, key_id, which):
        key = self.item(key_id)
        nxt = next((k for k in keys_of(self._owner(key), key["prop"]) if k["t"] > key["t"]), None)
        h = handles_of(key)
        if nxt is None or h is None or nxt["v"] == key["v"]:
            return False
        return self._begin("Move curve handle", {"key": key_id, "which": which, "h": h, "p0": (key["t"], key["v"]),
                                                 "p3": (nxt["t"], nxt["v"])})

    @Slot(float, float)
    def handleTo(self, t, v):
        """The handle's new place (seconds, field value): the key's custom ease with that handle's x, y from it."""
        if self._drag is None or "which" not in self._grab:
            return
        g = self._grab
        (t0, v0), (t1, v1) = g["p0"], g["p3"]
        args = {"ease": "custom", **g["h"]}
        args[X[g["which"] - 1]] = round(min(max((t - t0) / (t1 - t0), 0.0), 1.0), 3)
        args[Y[g["which"] - 1]] = round(min(max((v - v0) / (v1 - v0), -2.0), 3.0), 3)
        self.guard(lambda: self._drag.preview([{"op": "key.set", "target": [g["key"]], "args": args}]))

    @Slot(str, float, float)
    def askKeyMenu(self, key_id, gx, gy):
        """Right-click on a key: it is picked (unless already among the picks) and the key's Ease list opens there."""
        if key_id not in self.picked_keys():
            self.pick_key(key_id)
        self.b.keyBar.askMenu(gx, gy)

    def cancelDrag(self):
        """Esc mid-drag: the curve as at the press, nothing recorded."""
        d, self._drag, self._grab, self._frozen = self._drag, None, None, {}
        self.b.timeSnap.clear()
        if d is not None:
            self.guard(lambda: d.end(cancel=True))

    @Slot()
    def endDrag(self):
        d, self._drag, self._grab, self._frozen = self._drag, None, None, {}
        self.b.timeSnap.clear()                         # the label and the snap line go with the drag
        if d is not None:
            self.guard(lambda: self.done(d.end()))
