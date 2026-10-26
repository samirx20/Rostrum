"""Which layers the picture really shows, asked of the engine (ENGINE_CONTRACT.md § 1 `place`): where each layer is
drawn at a time, through its groups, the frame (camera, depth, tilt) and a drawing cycle's steps (loopStepX / Y), the
very transform the render draws with. A layer is on screen when its drawn outline reaches into the picture. Python
only does the cheap part first (is it in its times, not see-through, not a matte): the engine refuses undrawn layers.
"""
from __future__ import annotations

import re

from rostrum2d.engine import EngineError

_NUMBER = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
_REFUSED = re.compile(r'"([^"]+)" is not drawn')


def extent(place: dict) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) in comp px of the layer's true outline (its box when the outline is empty)."""
    nums = [float(x) for x in _NUMBER.findall(place.get("edge") or "")]
    if len(nums) >= 2:
        xs, ys = nums[0::2], nums[1::2]
        return min(xs), min(ys), max(xs), max(ys)
    m, w, h = place["m"], place["w"], place["h"]
    pts = []
    for x, y in ((0, 0), (w, 0), (w, h), (0, h)):
        d = m[6] * x + m[7] * y + m[8] or 1.0
        pts.append(((m[0] * x + m[1] * y + m[2]) / d, (m[3] * x + m[4] * y + m[5]) / d))
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


class Screen:
    """`seen(t, ids)`: the ids (layers Python thinks are drawn at t) whose outline reaches into the picture. `start` builds
    the engine's ask on first use, so a composition with nothing to check never starts one."""

    def __init__(self, start, width: float, height: float):
        self._start, self._ask, self.width, self.height = start, None, width, height

    def seen(self, t: float, ids) -> set[str]:
        ids = list(ids)
        if not ids:
            return set()
        if self._ask is None:
            self._ask = self._start()
        while True:
            try:
                places = self._ask(t, ids)
                break
            except EngineError as e:        # one layer the engine does not draw at t (a matte, a see-through group): leave it out
                named = _REFUSED.search(str(e))
                if not named or named.group(1) not in ids:
                    raise
                ids.remove(named.group(1))
                if not ids:
                    return set()
        out = set()
        for i, place in places.items():
            x0, y0, x1, y1 = extent(place)
            if x1 > 0 and y1 > 0 and x0 < self.width and y0 < self.height:
                out.add(i)
        return out
