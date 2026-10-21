"""Moving a time without changing how it is written: a time in seconds stays seconds, one in beats stays beats,
one on a marker stays on that marker ("#drop+0.25"). The one place that rule lives (the Timeline's drag and a
layered sound's group move both use it)."""
from __future__ import annotations

from . import tempo, times


def spb(root: dict, at: float = 0.0) -> float:
    """Seconds per beat at `at` seconds (the tempo map: tempo.py)."""
    return tempo.beat_seconds(root, at)


def write_like(old, t: float, root: dict):
    """`t` seconds, written in the form `old` was written in."""
    name = times.marker_ref(old)
    if name is not None:
        m = times.markers(root).get(name)
        if m is not None:
            off = round(t - times.seconds(m.get("at", 0), root, f"marker {name}"), 4)
            return f"#{name}" if abs(off) < 1e-6 else f"#{name}{off:+g}"
    if isinstance(old, dict) and "beat" in old:
        return {"beat": round(tempo.beat_at(root, t), 4)}
    return round(t, 4)
