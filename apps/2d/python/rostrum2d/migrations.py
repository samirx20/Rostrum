"""One small data-only step per change of the .mtn file format (rostrum_core DocKind.migrations): step n takes a
document saved as format n to format n+1, run on open before the document is checked. Raising `FORMAT` in kind.py
means adding its step here (the kind refuses to start without it).

    1 → 2   a Loop field written True / False (the first builds) becomes "loop" / "off" (looping.MODES)
    2 → 3   each scene gets its frame (the box that is exported, and its camera); cameras become the frame's keys,
            several cameras its cuts (frame/convert.py, apps/2d/FRAME.md › Older files)
    3 → 4   the document gets its list of paintings (paintings.py; empty: no older file has any, and the new fill
            fields' defaults draw exactly as before)
    4 → 5   a group's Width / Height hugs layers switches (hugWidth / hugHeight) become its size modes sizeW / sizeH:
            on = "fit", off = "fixed" (the auto layout became the engine's CSS layout, layout.py)
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


def paintings_list(data: dict, lists: dict):
    data.setdefault("paintings", [])
    return data, "Paintings list added"


def size_modes(data: dict, lists: dict):
    n = 0
    for item in walk(data, lists):
        if item.get("type") != "group":
            continue
        for old, new in (("hugWidth", "sizeW"), ("hugHeight", "sizeH")):
            if old in item:
                item[new] = "fit" if item.pop(old) else "fixed"
                n += 1
    return data, f"Hug switches written as size modes on {n} group side{'s' * (n != 1)}"


STEPS = {1: loop_words, 2: frames, 3: paintings_list, 4: size_modes}
FORMAT = len(STEPS) + 1
