"""One small data-only step per change of the .trk file format (rostrum_core DocKind.migrations): step n takes a
document saved as format n to format n+1, run on open before the document is checked. Raising `FORMAT` in kind.py
means adding its step here (the kind refuses to start without it).

    1 → 2   level matching (preset_level.py): the compiler now puts each instrument's measured gain under the track's
            volume, so every existing track's volume (and volume lane) is divided by that gain: the song renders
            exactly as before. The table is part of the format; changing a gain needs a step 2 → 3, never an edit.
"""
from __future__ import annotations

from . import preset_level

VOLUME_MAX = 4.0        # the fader's top (and the engine's)


def level_matched(data: dict, lists: dict):
    n, capped = 0, 0
    for t in data.get("tracks", []):
        g = preset_level.gain(t)
        if g == 1.0:
            continue
        n += 1
        if "volume" in t:
            was = t["volume"] / g
            t["volume"] = round(min(was, VOLUME_MAX), 6)
            capped += was > VOLUME_MAX
        for lane in t.get("automation", []):
            if lane.get("lane") == "volume":
                lane["points"] = preset_level.scaled(lane["points"], 1 / g, cap=VOLUME_MAX)
    said = f"Level matching: {n} track volume{'s' * (n != 1)} offset so the song sounds as before"
    return data, said + (f" ({capped} held at the fader's top, a little quieter)" if capped else "")


STEPS = {1: level_matched}
FORMAT = len(STEPS) + 1
