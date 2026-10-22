"""What a drag of a layer bar on the timeline asks of the document: where the dragged edge lands (a shared marker or
the playhead near it, else a whole frame) and the layer.shift / layer.trim call that gets it there. One BarGrab per
drag; drags.py holds it and previews its calls inside one gesture."""
from __future__ import annotations

PARTS = ("move", "start", "end")


class BarGrab:
    def __init__(self, layer: str, part: str, t0: float, start: float, end: float, fps: float, others=()):
        """`start` / `end` are the bar's edges when the drag began, `t0` the time under the pointer then (composition
        seconds). `others`: more selected layers a move takes along (each layer.shift by the same amount, one call)."""
        self.layer, self.part, self.t0, self.start, self.end, self.fps = layer, part, t0, start, end, fps
        self.others = list(others)
        self.applied = 0.0           # how far a move has been previewed so far (a shift is relative, previews pile up)
        self.on: str | None = None   # the shared marker the dragged edge sits on now

    def _edge(self, t: float, times: dict, playhead: float, within: float) -> float:
        """The dragged edge for the pointer at `t`: on a marker or the playhead when near, else on a whole frame."""
        raw = (self.end if self.part == "end" else self.start) + t - self.t0
        name, at = min(times.items(), key=lambda m: abs(m[1] - raw), default=(None, 0.0))
        if name is not None and abs(at - raw) <= within:
            self.on = name
            return at
        self.on = None
        return playhead if abs(playhead - raw) <= within else round(raw * self.fps) / self.fps

    def calls(self, t: float, times: dict, playhead: float, within: float) -> list[dict]:
        """The calls that bring the layer to the pointer at `t` from where the last call left it ([] = nothing to do)."""
        edge, one = self._edge(t, times, playhead, within), 1 / self.fps
        if self.part == "move":
            total = edge - self.start
            by, self.applied = round(total - self.applied, 6), total
            return [{**self._call("layer.shift", by=by), "target": [self.layer, *self.others]}] if by else []
        if self.part == "start":
            if edge > self.end - one:
                edge, self.on = self.end - one, None
            return [self._call("layer.trim", start=round(edge, 6))]
        if edge < self.start + one:
            edge, self.on = self.start + one, None
        return [self._call("layer.trim", end=round(edge, 6))]

    def tie_calls(self) -> list[dict]:
        """On release with the edge on a marker: tie the layer to it (nothing seen moves)."""
        if self.on is None or self.others:          # several bars: each keeps its own place (no one marker for all)
            return []
        ref = "#" + self.on
        return [self._call("layer.shift", to=ref) if self.part == "move" else self._call("layer.trim", **{self.part: ref})]

    def _call(self, op: str, **args) -> dict:
        return {"op": op, "target": [self.layer], "args": args}
