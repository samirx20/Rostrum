"""Sounds Rostrum no longer makes. Until 2026-10-23 a track could hold `sounds`: a click, riser, hit or sub drop
made from settings. Sam dropped them (PURPOSE.md: music first): a move is answered with instruments
(motion/score.py). An older song that still has one opens, and says so in plain words, naming each one (DocKind.warn:
the Problems chip, inspect, every agent reply); it is left out of the mix and kept in the file, never lost silently."""
from __future__ import annotations


def _when(at) -> str:
    return f"{at:g} s" if isinstance(at, (int, float)) else str(at)


def warn(data: dict) -> list[str]:
    """One sentence per made-from-settings sound an older song still holds, led by its track's id (the chip selects it)."""
    return [f'{t.get("id", "?")}: this song has a designed sound ("{s.get("design", "?")}" at {_when(s.get("at", "?"))}) '
            f"that Rostrum no longer makes; it is left out of the mix. Replace it with an instrument"
            for t in data.get("tracks", []) for s in t.get("sounds", []) or ()]
