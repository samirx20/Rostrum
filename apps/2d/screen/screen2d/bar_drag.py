"""What a drag of a layer bar on the timeline asks of the document: where the dragged edge lands (time_snap.py, the
one snapping in time: a marker, the playhead, other bars and keys, beats, else a whole frame) and the layer.shift /
layer.trim call that gets it there. One BarGrab per drag; drags.py holds it and previews its calls inside one gesture."""
from __future__ import annotations

from . import time_snap

PARTS = ("move", "start", "end")


class BarGrab:
    def __init__(self, layer: str, part: str, t0: float, start: float, end: float, fps: float, others=(), found=()):
        """`start` / `end` are the bar's edges when the drag began, `t0` the time under the pointer then (composition
        seconds). `others`: more selected layers a move takes along (each layer.shift by the same amount, one call).
        `found`: what the edge may snap to (time_snap.targets, worked out once when the drag began)."""
        self.layer, self.part, self.t0, self.start, self.end, self.fps = layer, part, t0, start, end, fps
        self.others, self.found = list(others), list(found)
        self.edge = end if part == "end" else start      # the dragged edge now (composition seconds)
        self.on: str | None = None   # the shared marker the dragged edge sits on now
        self.caught = None           # what the edge snapped to now (time_snap.Target), for the label
        self.moved = 0.0             # how far the dragged edge is from where it began, seconds

    def _edge(self, t: float, within: float) -> float:
        """The dragged edge for the pointer at `t` (time_snap.snap)."""
        was = self.end if self.part == "end" else self.start
        edge, self.caught = time_snap.snap(was + t - self.t0, self.found, within, self.fps)
        self.on = self.caught.name if self.caught is not None and self.caught.kind == "marker" else None
        return edge

    def calls(self, t: float, within: float, now: float) -> list[dict]:
        """The calls that bring the layer to the pointer at `t` ([] = nothing to do). `now`: the layer's start as the
        previews so far left it. A shift is relative and previews pile up, so each is measured from there: the edge
        lands exactly on its target (a beat, a whole frame), never a rounding off."""
        edge, one = self._edge(t, within), 1 / self.fps
        if self.part == "move":
            self.moved, self.edge = edge - self.start, edge
            by = round(edge - now, 6)
            return [{**self._call("layer.shift", by=by), "target": [self.layer, *self.others]}] if by else []
        if self.part == "start":
            if edge > self.end - one:
                edge, self.on, self.caught = self.end - one, None, None
            self.moved, self.edge = edge - self.start, edge
            return [self._call("layer.trim", start=round(edge, 6))]
        if edge < self.start + one:
            edge, self.on, self.caught = self.start + one, None, None
        self.moved, self.edge = edge - self.end, edge
        return [self._call("layer.trim", end=round(edge, 6))]

    def tie_calls(self) -> list[dict]:
        """On release with the edge on a marker: tie the layer to it (nothing seen moves)."""
        if self.on is None or self.others:          # several bars: each keeps its own place (no one marker for all)
            return []
        ref = "#" + self.on
        return [self._call("layer.shift", to=ref) if self.part == "move" else self._call("layer.trim", **{self.part: ref})]

    def _call(self, op: str, **args) -> dict:
        return {"op": op, "target": [self.layer], "args": args}
