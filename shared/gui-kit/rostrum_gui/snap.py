"""Snapping, the ONE rule for every app (INTERACTION.md 1.11): where a dragged value lands, what it caught, and the
words the drag label shows. One axis at a time (a time, or a canvas x or y); no Qt.

    caught = snap(t, targets, scale, free=mods.free, step=1 / fps)   # scale: screen px per unit (px per second, zoom)
    caught.value, caught.target                                       # where it lands; what it caught (None: nothing)
    label(frames(caught.value - t0, fps), caught)                     # "+6 f · drop"
    tie(caught.value, caught)                                         # "#drop" on a marker drop, else the number

**Distance:** 6 screen px at any zoom: the caller passes its scale and the kit turns 6 px into units, so at high zoom
you still place freely between targets. **Strength:** by kind, strongest first (RANK below, from 1.11's list); the
strongest kind within reach wins over a nearer target of a weaker kind, and among one kind the nearest wins (then the
one given first). **Nothing caught:** the value stays as dragged, or lands on the nearest `step` when one is given
(whole frames are always caught in time). **Off:** `free` (Ctrl held, or the Snap switch off) catches no target; a
`step` still applies. Snapping never touches a typed value: only drags call it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from rostrum_core.marker_times import write as marker_ref

DISTANCE = 6.0            # screen px, at any zoom (one number for one feel; Sound's 8 px was dropped, 1.11)

RANK = {                  # strongest first (INTERACTION 1.11). On a canvas the frame's edges and centre come first.
    "frame": 0,
    "marker": 1,
    "playhead": 2,
    "edge": 3, "centre": 3, "key": 3,                  # other items' edges, centres and keys
    "measure": 4, "section": 4,                        # music bars over beats (2D UX_SPEC 3.28), section edges
    "beat": 5, "guide": 5, "layout": 5, "spacing": 5,  # beats, guides, the layout grid, equal spacing
    "grid": 6,                                         # the grid
}


@dataclass(frozen=True)
class Target:
    """Something a drag may catch: its kind (a RANK key), the name the label and the magenta line show ("drop",
    "playhead", "Title start", "bar 2"), and where it is, in the caller's units (seconds, canvas px)."""
    kind: str
    name: str
    at: float

    def __post_init__(self):
        if self.kind not in RANK:
            raise ValueError(f'snap: "{self.kind}" is not a kind of snap target; '
                             f'use one of: {", ".join(RANK)}')
        if not isinstance(self.at, (int, float)) or not math.isfinite(self.at):
            raise ValueError(f'snap: target "{self.name}" has no place ({self.at!r}); give it a number')


@dataclass(frozen=True)
class Caught:
    value: float                  # where the dragged value lands
    target: Target | None         # what it caught (None: nothing; the step or the free value)

    @property
    def name(self) -> str:
        return self.target.name if self.target is not None else ""

    @property
    def on_marker(self) -> bool:
        return self.target is not None and self.target.kind == "marker"


def reach(scale: float) -> float:
    """The snap distance in the caller's units at `scale` screen px per unit. A zero or bad scale is a mistake."""
    if not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0:
        raise ValueError(f"snap: the scale must be screen px per unit, above 0 (got {scale!r})")
    return DISTANCE / scale


def snap(value: float, targets, scale: float, free: bool = False, step: float | None = None) -> Caught:
    """Where `value` lands (see the module help). `targets`: Target list, any order (strength is by kind)."""
    within = reach(scale)
    best = None
    if not free:
        for i, g in enumerate(targets):
            if not isinstance(g, Target):
                raise ValueError(f"snap: {g!r} is not a snap Target")
            d = abs(g.at - value)
            if d <= within and (best is None or (RANK[g.kind], d, i) < best[0]):
                best = ((RANK[g.kind], d, i), g)
    if best is not None:
        return Caught(best[1].at, best[1])
    if step is not None:
        if step <= 0:
            raise ValueError(f"snap: the step must be above 0 (got {step!r})")
        return Caught(round(value / step) * step, None)
    return Caught(value, None)


def frames(dt: float, fps: float) -> str:
    """An offset in whole frames: "+6 f", "−3 f", "0 f" (a true minus sign, so the label doesn't jump)."""
    if fps <= 0:
        raise ValueError(f"snap: frames per second must be above 0 (got {fps!r})")
    n = round(dt * fps)
    return f"+{n} f" if n > 0 else f"−{-n} f" if n < 0 else "0 f"


def label(words: str, caught: Caught | None) -> str:
    """The drag label: the value's words and, when it caught something, its name ("+6 f · drop")."""
    return f"{words} · {caught.name}" if caught is not None and caught.target is not None else words


def tie(value: float, caught: Caught | None):
    """What a time drag writes: on a marker drop, a tie to the marker ("#drop", or "#drop+0.2" for an offset from
    it; rostrum_core.marker_times is the one syntax), so the item follows when the marker moves; else the number."""
    if caught is not None and caught.on_marker:
        return marker_ref(caught.target.name, value - caught.target.at)
    return value
