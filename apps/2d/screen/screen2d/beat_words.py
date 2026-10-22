"""Times written as beats ("bar 5", "bar 5 beat 3") when the project's music has a tempo (UX_SPEC 3.28): the ONE place
a time on the screen becomes beat words. The key labels (hooks.label_of: "title · Opacity at bar 5"), the key bar's
Time ("bar 5 beat 3" beside it) and the time drag's snap label ("+6 f · bar 2 beat 3") all read `say` / `words`.

The grid is the music's own (`backend.soundtrack`: bar starts and beats in composition seconds, from RostrumSound). A
time within half a frame of a beat is on it; any other time, or a project with no tempo, has no beat words.
"""
from __future__ import annotations

from bisect import bisect_right


def words(t: float, beats: list[float], bars: list[float], fps: float) -> str:
    """"bar 5" on a bar's first beat, "bar 5 beat 3" on another beat, "" off the beats (composition seconds)."""
    near = 0.5 / fps
    on = next((i for i, b in enumerate(beats) if abs(b - t) <= near), None)
    if on is None:
        return ""
    if not bars or beats[on] < bars[0] - near:
        return f"beat {on + 1}" if not bars else ""          # no bars, or a pickup before bar 1
    bar = bisect_right(bars, beats[on] + near) - 1
    first = next(i for i, b in enumerate(beats) if b >= bars[bar] - near)
    n = on - first + 1
    return f"bar {bar + 1}" if n == 1 else f"bar {bar + 1} beat {n}"


def say(bridge, t: float) -> str:
    """Beat words for composition time `t` from the project's music ("" without a tempo or off the beats)."""
    sound = getattr(bridge, "soundtrack", None)
    if sound is None:
        return ""
    beats = sound.beat_times()
    return words(t, beats, sound.bar_times(), bridge.comp()["fps"]) if beats else ""
