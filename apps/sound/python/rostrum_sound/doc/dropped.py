"""Sounds Rostrum no longer makes. Until 2026-10-23 a track could hold `sounds`: a click, riser, hit or sub drop
made from settings. Sam dropped them (PURPOSE.md: music first): a move is answered with instruments
(motion/score.py). An older song that still has one opens, and says so in plain words, naming each one (DocKind.warn:
the Problems chip, inspect, every agent reply); it is left out of the mix and kept in the file, never lost silently."""
from __future__ import annotations

from .. import library


def _when(at) -> str:
    return f"{at:g} s" if isinstance(at, (int, float)) else str(at)


def warn(data: dict) -> list[str]:
    """One sentence per made-from-settings sound, and per retired transition recording, an older song still holds, led by its
    track's id (the chip selects it). A retired recording is still in the file and still plays; replace it."""
    gone = [f'{t.get("id", "?")}: clip "{c.get("id", "?")}" uses a {name} recording ({c.get("media")}) that Rostrum no longer offers; '
            f"replace it with an instrument or a real sound"
            for t in data.get("tracks", []) for c in t.get("clips", []) or ()
            if c.get("media") and (name := library.retired_name(str(c["media"])))]
    return gone + [f'{t.get("id", "?")}: this song has a designed sound ("{s.get("design", "?")}" at {_when(s.get("at", "?"))}) '
            f"that Rostrum no longer makes; it is left out of the mix. Replace it with an instrument"
            for t in data.get("tracks", []) for s in t.get("sounds", []) or ()]
