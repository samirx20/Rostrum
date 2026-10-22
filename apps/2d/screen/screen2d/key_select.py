"""The keys picked in the timeline (UX_SPEC 3.17 "Select, move …", INTERACTION 1.3, the list rule): click picks one,
Ctrl+click adds or removes one, Shift+click picks the run between on the same row. A diamond on a layer's bar stands
for every key of that layer at that frame, so it picks them all. Picked keys move together (one drag = one change),
Delete removes them (one change), Esc lets go of them before the layers (the Esc ladder). Screen state, never the
document; offered to QML as `backend.keys` (the kit's `attach`).

Keys never enter the kit's one selection (UX_SPEC 3.18 decision 5): the selection is the layers the keys belong to, so
the settings panel keeps showing the layer (the keyed settings highlighted: `props`) and the key bar alone shows the
keys. This set is its own state: Delete removes keys, not layers, while it holds any; picking other layers (or a
click on a row's empty part, or Esc) lets them go.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core.keys import keys_of, marked
from rostrum_gui.edits import Drag

from .bounds import layer_of


class KeySelect(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._ids, self._drag, self._own = bridge, [], None, False
        bridge.selectionChanged.connect(self._followed)
        bridge.docChanged.connect(self._prune)

    # ---- reads ------------------------------------------------------------------------------------------------
    @Property("QVariantList", notify=changed)
    def ids(self):
        return list(self._ids)

    @Property(int, notify=changed)
    def count(self):
        return len(self._ids)

    @Property("QVariantList", notify=changed)
    def props(self):
        """The settings the picked keys animate on the selected layer itself: its panel highlights those rows."""
        layer = self.b.selectedLayer
        return sorted({self.b.doc.item(k)["prop"] for k in self._ids
                       if self.b.doc.has(k) and self.b.doc.parent_of(k)[0] == layer})

    @Slot("QVariantList", result=bool)
    def has(self, ids):
        return bool(ids) and all(i in self._ids for i in ids)

    # ---- picking ----------------------------------------------------------------------------------------------
    @Slot("QVariantList", str, "QVariantList")
    def click(self, ids, how, row):
        """ids: the keys one diamond stands for; how: "" | "ctrl" | "shift"; row: every diamond's ids on its row, in
        time order (for Shift's run)."""
        ids = [str(i) for i in ids]
        if how == "ctrl":
            now = [i for i in self._ids if i not in ids] if self.has(ids) else self._ids + [i for i in ids if i not in self._ids]
        elif how == "shift" and self._ids:
            flat = [[str(i) for i in group] for group in row]
            at = [n for n, g in enumerate(flat) if any(i in self._ids for i in g)]
            here = next((n for n, g in enumerate(flat) if ids[0] in g), None)
            if at and here is not None:
                lo, hi = min(at[0], here), max(at[-1], here)
                now = self._ids + [i for g in flat[lo:hi + 1] for i in g if i not in self._ids]
            else:
                now = ids
        else:
            now = ids
        self._set(now)

    @Slot("QVariantList", str)
    def box(self, groups, how):
        """A box dragged over the timeline: every key it touches (groups: each diamond's ids). Ctrl or Shift adds
        them to the keys already picked (INTERACTION 1.3: a box picks what it touches)."""
        ids = [str(i) for g in groups for i in g]
        self._set(self._ids + ids if how in ("ctrl", "shift") else ids)

    @Slot()
    def clear(self):
        self._set([])

    def _set(self, ids):
        self._ids = list(dict.fromkeys(ids))
        layers = self._layers()
        if layers and set(layers) != set(self.b.selected_layers()):
            self._own = True                           # the keys' layers become the selection; the keys stay picked
            try:
                self.b.selectMany(layers)
            finally:
                self._own = False
        self.changed.emit()

    def _layers(self):
        return list(dict.fromkeys(layer_of(self.b.doc, k) for k in self._ids if self.b.doc.has(k)))

    def _followed(self):
        """Other layers (or nothing) picked: the keys are let go. A change that keeps the same layers keeps them."""
        if self._ids and not self._own and set(self._layers()) != set(self.b.selected_layers()):
            self._ids = []
            self.changed.emit()

    def _prune(self):
        gone = [i for i in self._ids if not self.b.doc.has(i)]
        if gone:
            self._ids = [i for i in self._ids if i not in gone]
            self.changed.emit()

    # ---- acting -----------------------------------------------------------------------------------------------
    @Slot(result=bool)
    def remove(self):
        """Delete: the picked keys go, one change."""
        if not self._ids:
            return False
        ids, self._ids = list(self._ids), []
        n = len(ids)
        ok = self.b.guard(lambda: self.b.done(self.b.doc.apply([{"op": "key.remove", "target": ids, "args": {}}], self.b.who,
                                                               label="Delete key" if n == 1 else f"Delete {n} keys"), ""))
        self.changed.emit()
        return ok

    @Slot(str, float, result=bool)
    def beginDrag(self, key_id, t0):
        """A press on a picked key (with others picked): they all move by the pointer's time change. t0: composition
        seconds under the pointer."""
        if key_id not in self._ids:
            return False
        grab = [(k, self.b.placed_item(k)) for k in self._ids]
        self._grab, self._t0 = [(k, dict(item)) for k, item in grab], t0

        def go():
            self._drag = Drag(self.b.doc, self.b.who, f"Move {len(self._ids)} keys")
        return self.b.guard(go)

    @Slot(str, float, result=bool)
    def beginStretch(self, key_id, t0):
        """Alt+press on the first or last picked key: dragging it stretches the picked keys in time around the other
        end (key.scale, one change). False for a key in the middle (then it is a plain move)."""
        times = {k: self.b.placed_item(k)["t"] for k in self._ids}
        if len(set(round(t, 6) for t in times.values())) < 2 or times.get(key_id) not in (min(times.values()), max(times.values())):
            return False
        self._stretch = (times[key_id], max(times.values()) if times[key_id] == min(times.values()) else min(times.values()))
        self._grab, self._t0 = [], t0

        def go():
            self._drag = Drag(self.b.doc, self.b.who, f"Stretch {len(self._ids)} keys")
        return self.b.guard(go)

    def _stretch_to(self, t):
        (held, around), fps = self._stretch, self.b.comp()["fps"]
        to = round((held + t - self._t0) * fps) / fps
        by = (to - around) / (held - around)
        if by < 0.01:
            return
        groups: dict[float, list[str]] = {}
        for k in self._ids:                 # one call per time origin (a layer timed from a marker counts from it)
            groups.setdefault(self.b.offset(self.b.doc.parent_of(k)[0]), []).append(k)
        calls = [{"op": "key.scale", "target": ids, "args": {"around": round(around - off, 6), "by": round(by, 6)}}
                 for off, ids in groups.items()]
        self.b.guard(lambda: self._drag.preview(calls))

    @Slot(float)
    def dragTo(self, t):
        if self._drag is None:
            return
        if not self._grab:                  # a stretch (beginStretch)
            return self._stretch_to(t)
        c = self.b.comp()
        dt = round((t - self._t0) * c["fps"]) / c["fps"]          # whole frames
        first = min(k["t"] for _, k in self._grab)
        last = max(k["t"] for _, k in self._grab)
        dt = min(max(dt, -first), c["duration"] - last)
        moving = {k for k, _ in self._grab}
        calls = []
        for kid, key in self._grab:
            owner = self.b.placed_item(self.b.doc.parent_of(kid)[0])
            t = key["t"] + dt
            if any(o["id"] not in moving and abs(o["t"] - t) < 1e-6 for o in keys_of(owner, key["prop"])):
                return                                            # another key of that setting is there: stay
            to = marked.moved(key["ref"], dt) if "ref" in key else t - self.b.offset(owner["id"])
            calls.append({"op": "key.set", "target": [kid], "args": {"t": to}})
        self.b.guard(lambda: self._drag.preview(calls))

    @Slot()
    def endDrag(self):
        d, self._drag = self._drag, None
        if d is not None:
            self.b.guard(lambda: self.b.done(d.end(), ""))
