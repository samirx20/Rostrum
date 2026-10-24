"""Moving keys in time on 3D's timeline: one key, the picked keys, or an item's whole bar (all its keys), one drag =
one change (key.set t on each, through one doc gesture). The grabbed key snaps (the kit's rostrum_gui/time_snap.py):
on a shared marker, the playhead or another item's key within the drag's reach (6 screen px; 0 = Ctrl held), else
the nearest whole frame; the "+6 f · logo lands" label and the snap line follow it (backend.timeSnap). Keys stay in
the shot (its start to its end); a move that would put a key on another key of its field is skipped. No Qt widgets.
"""
from __future__ import annotations

from rostrum_core.keys import keys_of
from rostrum_gui.edits import Drag
from rostrum_gui.time_snap import Target, snap

from . import outline


def targets(bridge, moving: set[str]) -> list[Target]:
    """What a time drag may catch now: the shared markers, the playhead, every key not being moved."""
    out = [Target("marker", m["name"], m["at"]) for m in bridge.marks.rows()]
    out.append(Target("playhead", "playhead", bridge.time))
    for it in outline.scene_items(bridge.doc.data):
        out.extend(Target("key", f"key · {outline.label_of(it)}", k["t"]) for k in it.get("keys", [])
                   if k["id"] not in moving and isinstance(k["t"], (int, float)))
    return out


class Mover:
    def __init__(self, bridge):
        self.b, self._drag, self._stretch = bridge, None, None

    @property
    def active(self) -> bool:
        return self._drag is not None

    def begin(self, ids: list[str], grab: str, label: str, t0: float | None = None) -> bool:
        """Start moving `ids` (keys); `grab`: the key the pointer holds (its time snaps), `t0`: the pointer's time."""
        self.end()
        doc = self.b.doc
        ids = [i for i in ids if doc.has(i) and doc.item(i).get("type") == "key"]
        if not ids or grab not in ids:
            return False
        self._ids, self._was = ids, {i: doc.item(i)["t"] for i in ids}
        self._t0 = self._was[grab] if t0 is None else t0
        self._grab, self._row = grab, doc.parent_of(grab)[0]
        self._found = targets(self.b, set(ids))

        def go():
            self._drag = Drag(doc, self.b.who, label)
        return self.b._guard(go)

    def begin_stretch(self, ids: list[str], grab: str, t0: float) -> bool:
        """Alt+drag the first or last of the picked keys `ids`: they stretch in time around the other end (key.scale, one
        change). False for a key in the middle, or keys all at one time (then it is a plain move)."""
        times = {i: self.b.doc.item(i)["t"] for i in ids if self.b.doc.has(i)}
        if grab not in times or len({round(t, 6) for t in times.values()}) < 2:
            return False
        held, lo, hi = times[grab], min(times.values()), max(times.values())
        if held not in (lo, hi) or not self.begin(list(times), grab, f"Stretch {len(times)} keys", t0):
            return False
        self._stretch, self._scaled = (held, hi if held == lo else lo), 1.0      # previews pile up: scale by what is left
        return True

    def _stretch_to(self, t: float, reach: float):
        held, around = self._stretch
        info = self.b.shot_info()
        fps = info["fps"]
        at, caught = snap(held + t - self._t0, self._found, reach, fps)
        at = min(max(at, info["start"] / fps), (info["end"] + 1) / fps)     # the moved end stays in the shot
        by = (at - around) / (held - around)
        if by < 0.01:
            return
        step, self._scaled = by / self._scaled, by
        self.b.timeSnap.show(at - held, fps, caught, at, self._row)
        self.b._guard(lambda: self._drag.preview([{"op": "key.scale", "target": self._ids, "args": {"around": around, "by": step}}]))

    def to(self, t: float, reach: float = 0.0):
        if self._drag is None:
            return
        if self._stretch:
            return self._stretch_to(t, reach)
        info, doc = self.b.shot_info(), self.b.doc
        fps = info["fps"]
        lo, hi = info["start"] / fps, (info["end"] + 1) / fps
        at, caught = snap(self._was[self._grab] + t - self._t0, self._found, reach, fps)
        dt = at - self._was[self._grab]
        dt = min(max(dt, lo - min(self._was.values())), hi - max(self._was.values()))    # every key stays in the shot
        new = {i: round(round((w + dt) * fps) / fps if caught is None else w + dt, 6) for i, w in self._was.items()}
        for i in self._ids:                            # never onto a key of the same field that stays put
            key = doc.item(i)
            owner = doc.item(doc.parent_of(i)[0])
            if any(k["id"] not in new and abs(k["t"] - new[i]) < 1e-6 for k in keys_of(owner, key["prop"])):
                return
        order = sorted(self._ids, key=lambda i: self._was[i], reverse=dt > 0)    # the far end first: none lands on another
        self.b.timeSnap.show(dt, fps, caught, new[self._grab], self._row)
        self.b._guard(lambda: self._drag.preview([{"op": "key.set", "target": [i], "args": {"t": new[i]}} for i in order]))

    def end(self):
        d, self._drag, self._stretch = self._drag, None, None
        self.b.timeSnap.clear()
        if d is not None:
            self.b._guard(lambda: self.b._done(d.end(), ""))
