"""Keys in time, the screen's side (a slot mix-in for Bridge2D): copy, cut and paste of keys picked in the timeline
(INTERACTION 1.8: Ctrl+V puts them at the playhead on the same settings of the selected layers, keeping their spacing;
key.paste, one change) and `,` / `.` (INTERACTION 1.7: the playhead to the previous / next thing that happens: a key,
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

    @Slot(result=bool)
    def pasteKeys(self):
        """The copied keys onto the selected layers, the first at the playhead (each layer's own seconds)."""
        keys, layers = self.keys_copied(), self.selected_layers()
        if not keys or not layers:
            self._set_status("Select the layers to paste the keys onto" if keys else "The copied keys are gone")
            return False
        calls = [{"op": "key.paste", "target": [lay], "args": {"from": keys, "at": round(self.own_t(lay), 6)}} for lay in layers]
        label = f"Paste {len(keys)} keys" + (f" on {len(layers)} layers" if len(layers) > 1 else "")
        return self._guard(lambda: self._apply(calls, label))

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
