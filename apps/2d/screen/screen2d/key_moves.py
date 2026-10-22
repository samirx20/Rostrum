"""Moving and stretching the picked keys in time (UX_SPEC 3.17): a drag moves them all by the pointer's change, Alt+drag
of the first or last stretches them around the other end (key.scale). The grabbed key snaps (time_snap.py: markers,
the playhead, other keys and bar ends, beats; else whole frames) and the "+6 f · drop" label follows the pointer.
One drag = one change. A slot mix-in for key_select.KeySelect (rostrum_gui/parts.py: listed before QObject).
"""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_core.keys import keys_of, marked
from rostrum_gui.edits import Drag

from . import time_snap
from .bounds import layer_of


class KeyMoves:
    def _begin(self, key_id, t0, label) -> bool:
        self._anchor, self._t0 = self.b.placed_item(key_id)["t"], t0
        self._row = layer_of(self.b.doc, key_id)          # the grabbed key's layer: the drag label's row
        self._found = time_snap.targets(self.b, skip_keys=self._ids)       # never snaps to the keys it moves

        def go():
            self._drag = Drag(self.b.doc, self.b.who, label)
        return self.b.guard(go)

    @Slot(str, float, result=bool)
    def beginDrag(self, key_id, t0):
        """A press on a picked key (with others picked): they all move by the pointer's time change. t0: composition
        seconds under the pointer."""
        if key_id not in self._ids:
            return False
        self._grab = [(k, dict(self.b.placed_item(k))) for k in self._ids]
        return self._begin(key_id, t0, f"Move {len(self._ids)} keys")

    @Slot(str, float, result=bool)
    def beginStretch(self, key_id, t0):
        """Alt+press on the first or last picked key: dragging it stretches the picked keys in time around the other
        end (key.scale, one change). False for a key in the middle (then it is a plain move)."""
        times = {k: self.b.placed_item(k)["t"] for k in self._ids}
        if len(set(round(t, 6) for t in times.values())) < 2 or times.get(key_id) not in (min(times.values()), max(times.values())):
            return False
        self._stretch = (times[key_id], max(times.values()) if times[key_id] == min(times.values()) else min(times.values()))
        self._grab, self._scaled = [], 1.0          # how far the previews have stretched so far (they pile up)
        return self._begin(key_id, t0, f"Stretch {len(self._ids)} keys")

    def _land(self, t, within):
        """Where the grabbed key lands for the pointer at `t`, and what it caught."""
        return time_snap.snap(self._anchor + t - self._t0, self._found, within, self.b.comp()["fps"])

    def _stretch_to(self, t, within):
        held, around = self._stretch
        to, caught = self._land(t, within)
        by = (to - around) / (held - around)
        if by < 0.01:
            return
        self.b.timeSnap.show(to - held, self.b.comp()["fps"], caught, to, self._row)
        groups: dict[float, list[str]] = {}
        for k in self._ids:                 # one call per time origin (a layer timed from a marker counts from it)
            groups.setdefault(self.b.offset(self.b.doc.parent_of(k)[0]), []).append(k)
        step, self._scaled = by / self._scaled, by    # a preview runs on top of the last: scale by what is left
        calls = [{"op": "key.scale", "target": ids, "args": {"around": round(around - off, 6), "by": step}}
                 for off, ids in groups.items()]
        self.b.guard(lambda: self._drag.preview(calls))

    @Slot(float)
    @Slot(float, float)
    def dragTo(self, t, within=0.0):
        """The pointer at `t` (composition seconds); `within`: the snap reach in seconds (6 px; 0 = Ctrl held: free)."""
        if self._drag is None:
            return
        if not self._grab:                  # a stretch (beginStretch)
            return self._stretch_to(t, within)
        c = self.b.comp()
        to, caught = self._land(t, within)
        dt = to - self._anchor
        first = min(k["t"] for _, k in self._grab)
        last = max(k["t"] for _, k in self._grab)
        if not -first <= dt <= c["duration"] - last:
            dt, caught = min(max(dt, -first), c["duration"] - last), None
        moving = {k for k, _ in self._grab}
        calls = []
        for kid, key in self._grab:
            owner = self.b.placed_item(self.b.doc.parent_of(kid)[0])
            t = key["t"] + dt
            if any(o["id"] not in moving and abs(o["t"] - t) < 1e-6 for o in keys_of(owner, key["prop"])):
                return                                            # another key of that setting is there: stay
            to = marked.moved(key["ref"], dt) if "ref" in key else t - self.b.offset(owner["id"])
            calls.append({"op": "key.set", "target": [kid], "args": {"t": to}})
        self.b.timeSnap.show(dt, c["fps"], caught, self._anchor + dt, self._row)
        self.b.guard(lambda: self._drag.preview(calls))

    @Slot()
    def endDrag(self):
        d, self._drag = self._drag, None
        self.b.timeSnap.clear()
        if d is not None:
            self.b.guard(lambda: self.b.done(d.end(), ""))
