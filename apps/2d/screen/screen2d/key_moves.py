"""Moving and stretching the picked keys in time (UX_SPEC 3.17): a drag moves them all by the pointer's change, Alt+drag
of the first or last stretches them around the other end (key.scale). The grabbed key snaps (time_snap.py: markers,
the playhead, other keys and bar ends, beats; else whole frames) and the "+6 f · drop" label follows the pointer.
One drag = one change. ← / → move them a frame (Shift: ten) through the same calls (`shift_calls`), one change per press.
A slot mix-in for key_select.KeySelect (rostrum_gui/parts.py: listed before QObject).
"""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_core.keys import keys_of, marked
from rostrum_gui.edits import Drag

from rostrum2d.retime import END, END_OF_COMP

from . import time_snap
from .bounds import layer_of


def ends_of(b, layers) -> dict:
    """The ends these layers had when a key drag began (`end_follows` needs them): only layers with an end of their
    own; one tied to a marker is left alone (its end is where it is on purpose)."""
    out = {}
    for lay in layers:
        item = b.placed_item(lay)
        if item.get("end", END_OF_COMP) < END_OF_COMP and not item.get(END):
            out[lay] = item["end"]
    return out


def end_follows(was: dict, latest: dict) -> list[dict]:
    """A key dragged past its layer's end takes the end along, so the key stays on the bar: the end is the later of what
    it was and the key's time (the one rule, for one key or many; `latest`: layer -> its furthest dragged key, in
    composition seconds). Drag the key back and the end goes back. Absolute, so previews don't pile up."""
    return [{"op": "layer.trim", "target": [lay], "args": {"end": round(max(end, latest[lay]), 6)}}
            for lay, end in was.items() if lay in latest]


def shift_calls(b, grab, dt, ends) -> list[dict] | None:
    """The calls that move the keys of `grab` ([(key id, its placed key at the start)]) by `dt` composition seconds:
    key.set {t} each (a key timed from a marker stays timed from it), the layers' ends following a key past them.
    None when a key would land on another key of its setting (it stays)."""
    moving = {k for k, _ in grab}
    calls, latest = [], {}
    for kid, key in grab:
        owner = b.placed_item(b.doc.parent_of(kid)[0])
        t = key["t"] + dt
        if any(o["id"] not in moving and abs(o["t"] - t) < 1e-6 for o in keys_of(owner, key["prop"])):
            return None
        to = marked.moved(key["ref"], dt) if "ref" in key else round(t - b.offset(owner["id"]), 6)
        calls.append({"op": "key.set", "target": [kid], "args": {"t": to}})
        lay = layer_of(b.doc, kid)
        latest[lay] = max(latest.get(lay, 0.0), t)
    return calls + end_follows(ends, latest)


def kept_in(dt, grab, duration) -> float:
    """`dt` held so the moved keys stay inside the composition (0 .. its length)."""
    first, last = min(k["t"] for _, k in grab), max(k["t"] for _, k in grab)
    return min(max(dt, -first), duration - last)


class KeyMoves:
    def _begin(self, key_id, t0, label) -> bool:
        self._anchor, self._t0 = self.b.placed_item(key_id)["t"], t0
        self._row = layer_of(self.b.doc, key_id)          # the grabbed key's layer: the drag label's row
        self._ends = ends_of(self.b, {layer_of(self.b.doc, k) for k in self._ids})   # what an end was: it follows a key past it
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
        dt = kept_in(to - self._anchor, self._grab, c["duration"])
        if dt != to - self._anchor:
            caught = None
        calls = shift_calls(self.b, self._grab, dt, self._ends)
        if calls is None:
            return                                                # another key of that setting is there: stay
        self.b.timeSnap.show(dt, c["fps"], caught, self._anchor + dt, self._row)
        self.b.guard(lambda: self._drag.preview(calls))

    @Slot()
    def endDrag(self):
        d, self._drag = self._drag, None
        self.b.timeSnap.clear()
        if d is not None:
            self.b.guard(lambda: self.b.done(d.end(), ""))

    @Slot(int, result=bool)
    def nudgeKeys(self, frames):
        """← / → with keys picked: they all move `frames` frames later (negative: earlier), one change per press."""
        if not self._ids:
            return False
        c = self.b.comp()
        grab = [(k, dict(self.b.placed_item(k))) for k in self._ids]
        dt = kept_in(frames / c["fps"], grab, c["duration"])
        if abs(dt) < 1e-9:
            self.b._set_status("The keys are at the " + ("start" if frames < 0 else "end"))
            return False
        calls = shift_calls(self.b, grab, dt, ends_of(self.b, {layer_of(self.b.doc, k) for k in self._ids}))
        if calls is None:
            self.b._set_status("Another key of that setting is there")
            return False
        n = len(grab)
        label = "Move a key" if n == 1 else f"Move {n} keys"
        return self.b.guard(lambda: self.b.done(self.b.doc.apply(calls, self.b.who, label=label, join=False), ""))
