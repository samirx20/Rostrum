"""The timeline's animation layers (rostrum_core.keys.layers), for QML as `backend.animLayers` (AnimLayers.qml): the
stack top first, the chosen layer (screen state: where a person's new keys go; "" = the Base), and the edits, each an
animlayer.* operation (one undo step; a weight slider's press-drag-release is one change). An app plugs it in with
its bridge (`doc`, `who`, `time`, `_apply`, `_guard`, `_done`, `docChanged`) and calls `rows_layer()` where it lists
keys, so the rows show the chosen layer's keys only.

While a layer is chosen, a person's key.add and value.set go on it as keys (`route`, a Document route: an agent's calls are never
touched). The value they set is what they see: on an add layer the key holds the offset that gives it, on a replace
layer the value that gives it at the layer's weight (a layer at weight 0 or off keys the value as given).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core.keys import keys_of, layers as L, track_value
from rostrum_core.keys.layers import stack_of

from .edits import Drag


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


class AnimLayers(QObject):
    changed = Signal()
    picked = Signal()                                # the chosen layer changed: the app lists its rows again

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b, self._active, self._drag = bridge, "", None
        bridge.doc.routes.append(self.route)
        bridge.docChanged.connect(self._on_doc)

    # ---- what QML reads ----------------------------------------------------------------------------------------
    def _stack(self) -> list[dict]:
        return stack_of(self.b.doc.data)

    @Property("QVariantList", notify=changed)
    def rows(self):
        """Top first: {id, name, weight (now), mode, on, faded (its weight has keys), active}."""
        t = self.b.time
        return [{"id": x["id"], "name": x.get("name", x["id"]), "weight": L.weight_at(x, t), "mode": x.get("mode", "add"),
                 "on": x.get("on", True), "faded": any(k.get("prop") == "weight" for k in x.get("keys", [])),
                 "active": x["id"] == self._active} for x in reversed(self._stack())]

    active = Property(str, lambda s: s._active, notify=changed)

    @Property(str, notify=changed)
    def activeName(self):
        x = next((x for x in self._stack() if x["id"] == self._active), None)
        return x.get("name", x["id"]) if x else ""

    count = Property(int, lambda s: len(s._stack()), notify=changed)

    def rows_layer(self) -> str:
        return self._active

    # ---- edits -------------------------------------------------------------------------------------------------
    def _run(self, calls, label):
        self.b._guard(lambda: self.b._apply(calls, label))

    @Slot()
    def add(self):
        before = {x["id"] for x in self._stack()}
        self._run([{"op": "animlayer.add", "target": [], "args": {}}], "New layer")
        made = [x["id"] for x in self._stack() if x["id"] not in before]
        if made:
            self.pick(made[0])

    @Slot(str)
    def pick(self, id_):
        self._active = id_ if any(x["id"] == id_ for x in self._stack()) else ""
        self.changed.emit()
        self.picked.emit()                           # the app's rows show this layer's keys

    def _set(self, id_, label, **args):
        self._run([{"op": "animlayer.set", "target": [id_], "args": args}], label)

    @Slot(str, str)
    def rename(self, id_, name):
        if name.strip():
            self._set(id_, "Rename layer", name=name.strip())

    @Slot(str, str)
    def setMode(self, id_, mode):
        self._set(id_, "Layer mode", mode=mode)

    @Slot(str, bool)
    def setOn(self, id_, on):
        self._set(id_, "Layer on" if on else "Layer off", on=bool(on))

    def _weight_args(self, id_, w):
        x = next(x for x in self._stack() if x["id"] == id_)
        faded = any(k.get("prop") == "weight" for k in x.get("keys", []))
        return {"weight": round(float(w), 3), **({"at": round(self.b.time, 6)} if faded else {})}

    @Slot(str, float)
    def setWeight(self, id_, w):
        self._set(id_, "Layer weight", **self._weight_args(id_, w))

    @Slot(str)
    def keyWeight(self, id_):
        """A weight key at the playhead (its weight now): from then on the slider keys the weight where the playhead is."""
        x = next(x for x in self._stack() if x["id"] == id_)
        self._set(id_, "Key layer weight", weight=L.weight_at(x, self.b.time), at=round(self.b.time, 6))

    @Slot(str)
    def beginWeight(self, id_):
        self.endWeight()
        self._wid = id_
        self.b._guard(lambda: setattr(self, "_drag", Drag(self.b.doc, self.b.who, "Layer weight")))

    @Slot(float)
    def weightTo(self, w):
        if self._drag is not None:
            calls = [{"op": "animlayer.set", "target": [self._wid], "args": self._weight_args(self._wid, w)}]
            self.b._guard(lambda: self._drag.preview(calls))

    @Slot()
    def endWeight(self):
        d, self._drag = self._drag, None
        if d is not None:
            self.b._guard(lambda: self.b._done(d.end(), ""))

    @Slot(str)
    def remove(self, id_):
        self._run([{"op": "animlayer.remove", "target": [id_], "args": {}}], "Delete layer")

    @Slot(str, int)
    def move(self, id_, by):
        """`by` +1: one up the stack (shown higher), -1: one down."""
        ids = [x["id"] for x in self._stack()]
        to = ids.index(id_) + by
        if 0 <= to < len(ids):
            self._run([{"op": "animlayer.move", "target": [id_], "args": {"to": to}}], "Move layer")

    # ---- the route: a person's new keys go on the chosen layer ------------------------------------------------
    def route(self, calls):
        layer = next((x for x in self._stack() if x["id"] == self._active), None)
        if layer is None:
            return calls
        out = []
        for c in calls:
            args = c.get("args", {})
            if c.get("op") == "value.set" and not ({"by", "layer"} & args.keys()) and "prop" in args:
                at = args.get("at", round(self.b.time, 6))      # a value set now is a key on the layer now
                c = {**c, "op": "key.add", "args": {k: v for k, v in {**args, "t": at}.items() if k != "at"}}
            if c.get("op") != "key.add" or "layer" in c.get("args", {}):
                out.append(c)
            else:                                    # one call per item: each one's offset is its own
                out += [self._on_layer({**c, "target": [t]}, layer) for t in c.get("target", [])]
        return out

    def _on_layer(self, call, layer):
        args = {**call.get("args", {}), "layer": layer["id"]}
        if "fields" not in args and _number(args.get("v")) and _number(args.get("t")):
            w = L.weight_at(layer, args["t"]) if layer.get("on", True) else 0.0
            if w > 0:
                return {**call, "args": {**args, "v": self._offset(call, layer, args, w)}}
        return {**call, "args": args}

    def _offset(self, call, layer, args, w) -> float:
        """The layer key that makes the field show `v` now: its curve now + what is missing, over the weight."""
        prop, t = args["prop"], args["t"]
        owner = self.b.doc.item(call["target"][0])
        base = track_value(keys, t) if (keys := keys_of(owner, prop)) else owner.get(prop)
        if not _number(base):
            return args["v"]
        shown = L.value(owner, prop, t, self._stack(), base)
        mine = L.layer_keys(owner, prop, layer["id"])
        now = track_value(mine, t) if mine else (0.0 if layer.get("mode", "add") == "add" else shown)
        return round(now + (args["v"] - shown) / w, 6)

    def _on_doc(self):
        if self._active and not any(x["id"] == self._active for x in self._stack()):
            self._active = ""                        # an undo took the chosen layer away: back to the Base
            self.picked.emit()
        self.changed.emit()
