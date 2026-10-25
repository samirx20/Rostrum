"""A drawing cycle: a drawing layer's run of drawings repeated (Loop: loop or ping-pong, drawing.py `cycle`), as data on
the layer, never copied drawings. Two settings shape the repeats:

- `loopTimes`: how many times the run plays (0 = until the layer ends); after that the drawing last shown holds.
- `loopStepX` / `loopStepY` (Loop only): how far each repeat sits from the one before, in the drawing's own canvas px.
  A walk drawn travelling across its canvas (feet planted) repeats one stride further on each time, so the feet never
  slide. Sent as the layer's anchor moved back by the step at each repeat (the anchor is in canvas px, so the step
  turns and scales with the layer); an anchor with keys of its own is sampled on every frame.

Which drawing shows at a frame is drawing.frame_at (it reads `loopTimes`); this module adds the steps to the scene.
"""
from __future__ import annotations

import math

from rostrum_core.keys import track_value

from . import looping

FIELDS = ("loopTimes", "loopStepX", "loopStepY")       # Python only: the engine gets explicit frames and anchor keys


def times(drawing: dict) -> int:
    return int(drawing.get("loopTimes") or 0)


def held_from(drawing: dict, start: int, length: int) -> int | None:  # noqa: ARG001  (start: called with the run)
    """The cycle's place (frames from its start) from which the run is over and the last shown drawing holds; None
    when it repeats to the layer's end."""
    return times(drawing) * length if times(drawing) else None


def repeat_of(drawing: dict, n: int, start: int, length: int) -> int:
    """Which repeat frame `n` is in: 0 for the first play (and before it), counting up, kept within loopTimes."""
    k = max(0, (n - start) // length)
    return min(k, times(drawing) - 1) if times(drawing) else k


def step(node: dict, drawing: dict, run: tuple[int, int] | None, size: tuple[int, int], fps: float, until: float) -> None:
    """The node's anchor moved back one step at each repeat (see the module's words); nothing without a step."""
    if run is None or looping.mode_of(drawing.get("loop")) != "loop":
        return
    start, length = run
    last = math.ceil(until * fps)
    for prop, by, px in (("anchorX", drawing.get("loopStepX") or 0.0, size[0]), ("anchorY", drawing.get("loopStepY") or 0.0, size[1])):
        if not by:
            continue
        own = node.get("anim", {}).get(prop)
        base = node["props"][prop]
        if own:                         # the anchor's own keys, plus the step: every frame
            keys = [{"t": f / fps, "v": track_value(own, f / fps) - repeat_of(drawing, f, start, length) * by / px, "ease": "hold"}
                    for f in range(last + 1)]
        else:                           # one hold key where each repeat starts
            ends = range(start + length, last + 1, length)
            keys = [{"t": 0.0, "v": base, "ease": "hold"}] + [
                {"t": f / fps, "v": base - repeat_of(drawing, f, start, length) * by / px, "ease": "hold"} for f in ends
                if repeat_of(drawing, f, start, length) > repeat_of(drawing, f - 1, start, length)]
        if len(keys) > 1:
            node.setdefault("anim", {})[prop] = keys
