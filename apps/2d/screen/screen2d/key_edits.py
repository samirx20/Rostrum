"""Keys in time, the screen's side (a slot mix-in for Bridge2D): copy, cut and paste of keys picked in the timeline
(INTERACTION 1.8: Ctrl+V puts them at the playhead on the same settings of the selected layers, keeping their spacing;
Ctrl+Shift+V at the times they were copied from; key.paste, one change), Ctrl+D (copies right after the last of them)
and the arrows on picked keys (`key_jobs`: the jobs that act on keys while the pick is about keys, key_select.about), and `,` / `.` (INTERACTION 1.7: the playhead to the previous / next thing that happens: a key,
a marker, a drawing, a layer's start or end; of the selected layers, or of everything when none is selected).

The keys copied are screen state (their ids), not the system clipboard: the latest copy wins, so copying layers after
keys pastes layers (clipboard.py clears this).
"""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum2d import fields as F
from rostrum_gui.parts import SlotMixin

from . import framing


class KeyEdits(SlotMixin):
    _key_clip: list = []

    def key_jobs(self) -> dict:
        """What each key-map job does while the pick is about keys (key_select.about): the one table the keys, the menus
        and Ctrl+K go through (KeyHub). ↑ / ↓ do nothing to keys (a key's value is changed in its box)."""
        k = self._keys
        out = {"copy": self.copyKeys, "cut": self.cutKeys, "duplicate": self.duplicateKeys, "delete": k.remove}
        for name, n in (("left", -1), ("right", 1)):
            out[f"nudge_{name}"], out[f"nudge_{name}_big"] = (lambda n=n: k.nudgeKeys(n)), (lambda n=n: k.nudgeKeys(10 * n))
        out |= {f"nudge_{d}{s}": (lambda: False) for d in ("up", "down") for s in ("", "_big")}
        return out

    def keys_take(self, job: str) -> bool:
        """The pick is about keys and this job acts on keys: it ran on them (True); else the layers' action runs."""
        do = self.key_jobs().get(job) if self._keys.about == "keys" else None
        if do is None:
            return False
        do()
        return True

    def keys_copied(self) -> list[str]:
        return [k for k in self._key_clip if self.doc.has(k)]

    @Slot(result=bool)
    def copyKeys(self):
        ids = self._keys.ids
        if not ids:
            return False
        self._key_clip = list(ids)
        self._set_status(f"Copied {len(ids)} key{'s' if len(ids) > 1 else ''}: select layers, move the playhead, Ctrl+V")
        self._hub.refresh()
        return True

    @Slot(result=bool)
    def cutKeys(self):
        return self.copyKeys() and self._keys.remove()

    def _paste_lacks(self, keys: list[str], layer_id: str) -> list[str]:
        """The settings of the copied keys that this layer has not (a rectangle has no text Size; a camera no Opacity),
        as the person reads them."""
        kind = self.doc.item(layer_id)["type"]
        have = set(F.animatable(kind))
        out = []
        for p in dict.fromkeys(self.doc.item(k)["prop"] for k in keys):
            if p not in have:
                known = next((q for q in (F.param(t, p) for t in F.FIELDS) if q), None)     # its words, from any kind that has it
                out.append(known.label if known else p)
        return out

    @Slot(result=bool)
    @Slot(str, result=bool)
    def pasteKeys(self, at="playhead"):
        """The copied keys onto the selected layers, the first at the playhead (each layer's own seconds); at
        "original": each at the time it was copied from. A layer that has not a copied setting gets nothing and is
        named in the top bar, never skipped silently."""
        keys, layers = self.keys_copied(), self.selected_layers()
        if not keys or not layers:
            self._set_status("Select the layers to paste the keys onto" if keys else "The copied keys are gone")
            return False
        lacks = {lay: self._paste_lacks(keys, lay) for lay in layers}
        name = lambda lay: self.doc.item(lay).get("name") or lay          # noqa: E731
        left = [lay for lay in layers if not lacks[lay]]
        said = "; ".join(f"{name(lay)} has no {' or '.join(w)}" for lay, w in lacks.items() if w)
        if not left:
            self._set_status(f"Can't paste these keys: {said}")
            return False
        first = min(self.placed_item(k)["t"] for k in keys) if at == "original" else self._t     # composition seconds
        calls = [{"op": "key.paste", "target": [lay], "args": {"from": keys, "at": round(self.own_t(lay, first), 6)}} for lay in left]
        label = f"Paste {len(keys)} keys" + (f" on {len(left)} layers" if len(left) > 1 else "")
        ok = self._guard(lambda: self._apply(calls, label))
        if ok and said:
            self._set_status(f"Pasted on {', '.join(name(lay) for lay in left)}; not on the others: {said}")
        return ok

    @Slot(result=bool)
    def duplicateKeys(self):
        """Ctrl+D with keys picked: copies of them right after the last of them (a frame on, spacing kept), on the
        settings they are on, one change; the copies are picked then, so Ctrl+D again repeats."""
        ids = [k for k in self._keys.ids if self.doc.has(k)]
        if not ids:
            return False
        times = {k: self.placed_item(k)["t"] for k in ids}
        by = max(times.values()) - min(times.values()) + 1 / self.comp()["fps"]
        owners: dict[str, list[str]] = {}
        for k in ids:
            owners.setdefault(self.doc.parent_of(k)[0], []).append(k)
        calls = [{"op": "key.paste", "target": [o], "args": {"from": ks, "at": round(self.own_t(o, min(times[k] for k in ks) + by), 6)}}
                 for o, ks in owners.items()]
        before = {k["id"] for o in owners for k in self.doc.item(o).get("keys", [])}
        if not self._guard(lambda: self._apply(calls, "Duplicate a key" if len(ids) == 1 else f"Duplicate {len(ids)} keys")):
            return False
        self._keys.click([k["id"] for o in owners for k in self.doc.item(o).get("keys", []) if k["id"] not in before], "", [])
        n = len(ids)          # said every time: the layer still looks picked, and Ctrl+D copying keys surprised people
        self._set_status(f"Copied {n} key{'s' if n > 1 else ''}: keys are picked. Esc, or click the layer, to copy the layer")
        return True

    # ---- , and . ------------------------------------------------------------------------------------------------
    def event_times(self) -> list[float]:
        """Every moment something happens, composition seconds, sorted: keys, markers, drawings, layer starts and
        ends; of the selected layers (and what is inside them), or of the whole composition."""
        comp, fps = self.placed(), self.comp()["fps"]
        picked = set(self.selected_layers())
        out = set(self.marks.times.values()) if self.marks and self.marks.times else set()

        def walk(layers, inside):
            for lay in layers:
                mine = inside or not picked or lay["id"] in picked
                if mine:
                    for o in (lay, *lay.get("effects", []), *lay.get("masks", [])):
                        out.update(k["t"] for k in o.get("keys", []) if isinstance(k["t"], (int, float)))
                    if F.param(lay["type"], "start") is not None:
                        out.update(t for t in (lay.get("start", 0.0), lay.get("end")) if isinstance(t, (int, float)))
                    if lay.get("frames"):
                        out.update(m["t0"] for m in framing.marks(lay, fps, comp["duration"]))
                walk(lay.get("layers", []), mine and bool(picked))
        walk(comp.get("layers", []), False)
        return sorted(t for t in out if 0 <= t <= comp["duration"])

    @Slot(int, result=bool)
    def stepEvent(self, direction):
        """`,` (-1) / `.` (+1): the playhead to the previous / next moment (a frame apart at least)."""
        half = 0.5 / self.comp()["fps"]
        times = self.event_times()
        to = next((t for t in reversed(times) if t < self._t - half), None) if direction < 0 else \
            next((t for t in times if t > self._t + half), None)
        if to is None:
            return False
        self.setTime(to)
        return True
