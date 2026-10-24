"""One small data-only step per change of the .mtn file format (rostrum_core DocKind.migrations): step n takes a
document saved as format n to format n+1, run on open before the document is checked. Raising `FORMAT` in kind.py
means adding its step here (the kind refuses to start without it).

    1 → 2   a Loop field written True / False (the first builds) becomes "loop" / "off" (looping.MODES)
    2 → 3   each scene gets its frame (the box that is exported, and its camera); cameras become the frame's keys,
            several cameras its cuts (frame/convert.py, apps/2d/FRAME.md › Older files)
"""
from __future__ import annotations

from rostrum_core.tree import walk

from .frame.convert import convert as frames


def loop_words(data: dict, lists: dict):
    n = 0
    for item in walk(data, lists):
        if isinstance(item.get("loop"), bool):
            item["loop"] = "loop" if item["loop"] else "off"
            n += 1
    return data, f"Loop written as words on {n} item{'s' * (n != 1)}"


STEPS = {1: loop_words, 2: frames}
FORMAT = len(STEPS) + 1
