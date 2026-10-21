"""The curve editor's data and drags (Animate page, the timeline's Curves view). Every change is an operation: a key drag is
`key.set` {t, v}, a handle drag is `key.handles`; each drag is one doc.gesture = one undo step.

The curves are those of the selected layer's animated number fields (its effects' and masks' too), sampled from the one
evaluation (ops_keys.curve_of). Each field has its own colour. Handles show only where an ease has them (a named cubic or
custom) and only for the selected key's stretches, so a dragged named cubic becomes `custom` from that curve's numbers.
Times and values from QML are seconds and field values; the view's value range is frozen while a drag runs.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d import fields as F
from rostrum_core.keys import keys_of, marked
from rostrum2d.ops_keys import curve_of, handles_of
from rostrum_gui.edits import Drag

from .outline import _fields, label_of

COLORS = ["#ff7a6b", "#f2b33d", "#4cc38a", "#4cc9e0", "#b48cff", "#ff7ac6"]
X, Y = ("x1", "x2"), ("y1", "y2")


def _stretch(k0: dict, k1: dict, h: dict) -> dict:
    """The stretch from key k0 to k1 with its two handles' places in (seconds, value)."""
    dt, dv = k1["t"] - k0["t"], k1["v"] - k0["v"]
    return {"key": k0["id"], "p0": [k0["t"], k0["v"]], "p3": [k1["t"], k1["v"]],
            "h1": [k0["t"] + h["x1"] * dt, k0["v"] + h["y1"] * dv], "h2": [k0["t"] + h["x2"] * dt, k0["v"] + h["y2"] * dv]}


def _range(samples, stretches):
    """The value range a view needs: the curve and every handle of a Bézier stretch, with some air."""
    vs = [s[1] for s in samples] + [v for s in stretches for v in (s["h1"][1], s["h2"][1])]
    lo, hi = min(vs), max(vs)
    pad = (hi - lo) * 0.12 or 1.0
    return lo - pad, hi + pad


class Curves(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._on, self._hidden, self._drag, self._grab, self._frozen = bridge, False, set(), None, None, {}
        bridge.outlineChanged.connect(self.changed)

    @Property(bool, notify=changed)
    def on(self):
        return self._on

    @Slot(bool)
    def setOn(self, on):
        self._on = on
        self.changed.emit()

    @Slot(str)
    def toggleField(self, field_id):
        self._hidden ^= {field_id}
        self.changed.emit()

    def _numbers(self):
        """[(owner, prop)] of the selected layer's animated number fields, in field-table order."""
        layer = self.b.selectedLayer
        if not layer:
            return []
        return [(o, p) for o, p in _fields(self.b.placed_item(layer)) if "v" in keys_of(o, p)[0]]

    @Property("QVariantList", notify=changed)
    def fields(self):
        """One entry per curve: id, label, colour, range lo..hi, shown, path [[t, v] …], keys, stretches (handles)."""
        out, sel, layer = [], self.b._sel, self.b.selectedLayer
        for n, (owner, prop) in enumerate(self._numbers()):
            fid, c, ks = f"{owner['id']}.{prop}", curve_of(owner, prop), keys_of(owner, prop)
            on = next((i for i, k in enumerate(ks) if k["id"] == sel), None)
            around = {on, None if on is None else on - 1} - {None, -1}
            pairs = [(ks[i], ks[i + 1], handles_of(ks[i])) for i in range(len(ks) - 1)]
            flat = [_stretch(a, b, h) for a, b, h in pairs if h and a["v"] != b["v"]]
            show = [_stretch(a, b, h) for i, (a, b, h) in enumerate(pairs) if i in around and h and a["v"] != b["v"]]
            name = F.param(owner["type"], prop).label
            out.append({"id": fid, "label": name if owner["id"] == layer else f"{label_of(owner)} · {name}",
                        "color": COLORS[n % len(COLORS)], "shown": fid not in self._hidden, "selected": on is not None,
                        "lo": (self._frozen.get(fid) or _range(c["samples"], flat))[0],
                        "hi": (self._frozen.get(fid) or _range(c["samples"], flat))[1],
                        "path": c["samples"], "stretches": show if fid not in self._hidden else [],
                        "keys": [{"id": k["id"], "t": k["t"], "v": k["v"], "sel": k["id"] == sel,
                                  "marker": marked.label(k["ref"]) if "ref" in k else ""} for k in ks]})
        return out

    # ---- drags: one gesture each ------------------------------------------------------------------------------
    def _begin(self, label, grab) -> bool:
        self.endDrag()
        self._frozen = {f["id"]: (f["lo"], f["hi"]) for f in self.fields}

        def go():
            self._drag, self._grab = Drag(self.b.doc, self.b.who, label), grab
        return self.b.guard(go)

    @Slot(str, result=bool)
    def beginKeyDrag(self, key_id):
        self.b.select(key_id)
        return self._begin("Move key", {"key": key_id})

    @Slot(float, float)
    def keyTo(self, t, v):
        """The key's new time and value (seconds, field value): key.set. Another key's time is not taken."""
        if self._drag is None or "which" in self._grab:
            return
        c, doc = self.b.comp(), self.b.doc
        key = self.b.placed_item(self._grab["key"])
        owner = self.b.placed_item(doc.parent_of(key["id"])[0])
        t = min(max(round(t * c["fps"]) / c["fps"], 0.0), c["duration"])
        if any(k["id"] != key["id"] and abs(k["t"] - t) < 1e-6 for k in keys_of(owner, key["prop"])):
            t = key["t"]
        p = F.param(owner["type"], key["prop"])
        lo, hi = (p.min if p.min is not None else -1e9), (p.max if p.max is not None else 1e9)
        args = {"t": marked.moved(key["ref"], t - key["t"]) if "ref" in key else t,   # on a marker: stays on it
                "v": round(min(max(v, lo), hi), 4)}
        self.b.guard(lambda: self._drag.preview([{"op": "key.set", "target": [key["id"]], "args": args}]))

    @Slot(str, int, result=bool)
    def beginHandleDrag(self, key_id, which):
        doc = self.b.doc
        key = self.b.placed_item(key_id)
        nxt = next((k for k in keys_of(self.b.placed_item(doc.parent_of(key_id)[0]), key["prop"]) if k["t"] > key["t"]), None)
        h = handles_of(key)
        if nxt is None or h is None or nxt["v"] == key["v"]:
            return False
        return self._begin("Move curve handle", {"key": key_id, "which": which, "h": h, "p0": (key["t"], key["v"]),
                                                 "p3": (nxt["t"], nxt["v"])})

    @Slot(float, float)
    def handleTo(self, t, v):
        """The handle's new place (seconds, field value): key.handles with that handle's x, y from it."""
        if self._drag is None or "which" not in self._grab:
            return
        g = self._grab
        (t0, v0), (t1, v1) = g["p0"], g["p3"]
        args = dict(g["h"])
        args[X[g["which"] - 1]] = round(min(max((t - t0) / (t1 - t0), 0.0), 1.0), 3)
        args[Y[g["which"] - 1]] = round(min(max((v - v0) / (v1 - v0), -2.0), 3.0), 3)
        self.b.guard(lambda: self._drag.preview([{"op": "key.handles", "target": [g["key"]], "args": args}]))

    @Slot()
    def endDrag(self):
        d, self._drag, self._grab, self._frozen = self._drag, None, None, {}
        if d is not None:
            self.b.guard(lambda: self.b.done(d.end(), ""))


# ---- screen steps (steps.py) -------------------------------------------------------------------------------------
def steps_curves(bridge, step, rest):
    """curves on|off | curvedrag <key> <dt s> <dv value> | handledrag <key> <1|2> <dx> <dy> (dx, dy: change of that
    handle's x / y in the curve's own 0..1 units). Each moves in two steps, as a hand would."""
    word, cv = step.split()[0], bridge.curves
    if word == "curves":
        cv.setOn(rest[0] == "on")
        return
    key = bridge.placed_item(rest[0])          # keys on a marker: at their seconds
    if word == "curvedrag":
        cv.beginKeyDrag(key["id"])
        for f in (0.5, 1.0):
            cv.keyTo(key["t"] + float(rest[1]) * f, key["v"] + float(rest[2]) * f)
    else:
        which, dx, dy = int(rest[1]), float(rest[2]), float(rest[3])
        if not cv.beginHandleDrag(key["id"], which):
            raise RuntimeError(f"step {step!r}: that key has no handles on its stretch")
        g = cv._grab
        (t0, v0), (t1, v1), h = g["p0"], g["p3"], g["h"]
        x0, y0 = h[X[which - 1]], h[Y[which - 1]]
        for f in (0.5, 1.0):
            cv.handleTo(t0 + (x0 + dx * f) * (t1 - t0), v0 + (y0 + dy * f) * (v1 - v0))
    cv.endDrag()
