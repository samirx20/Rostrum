"""Which of the project's sound plays with a scene: the one answer for the screen's Sound row, inspect_soundtrack, the
inspector's Soundtrack choice and an MP4 export's sound (AGENTS.md rule 9; the sound itself is RostrumSound's).

The scene's `soundtrack` field names a Sound item; empty = the project's main mix (rostrum_core.project.main: the
item marked main in project.json, else the first Sound item by name). No Qt.
"""
from __future__ import annotations

from rostrum_core import project


def main_mix(folder) -> dict | None:
    """The project's main mix ({id, name, file}), or None when the project has no Sound item (a stale mark is loud)."""
    return project.main(folder, "sound") if folder else None


def song(folder, chosen: str = "") -> dict | None:
    """The Sound item that plays: `chosen` (a scene's `soundtrack`) when set, else the main mix; None: no sound."""
    if not folder:
        return None
    from rostrum_sound import soundtrack
    if chosen:
        return soundtrack.find(folder, chosen)
    m = main_mix(folder)
    return soundtrack.find(folder, m["id"]) if m else None


def for_export(folder, chosen: str, fmt: str, asked: bool | None) -> str | None:
    """The Sound item an export puts under its picture, or None (silent). `asked` None = the default: on for an MP4 when
    the project has sound. Asked for where there is none is a loud error, never a silent file."""
    if asked is False or (asked is None and fmt != "mp4"):
        return None
    s = song(folder, chosen)
    if s is None and asked:
        from rostrum_core import RostrumError, codes
        raise RostrumError(codes.BAD_ARGUMENT, "export", "sound", "was asked, but the project has no RostrumSound item",
                           hint="Make the sound in RostrumSound first, or export without sound.")
    return s["id"] if s else None


_BEATS: dict = {}       # (song's stamp, seconds) -> beat times: describe() runs on every edit, the song's file rarely changes


def beats(folder, chosen: str, seconds: float) -> list[float] | None:
    """Every beat of the song that plays, 0 to `seconds` (RostrumSound's tempo grid: the one source, also behind the Sound
    row's beat lines), for an expression's pulse(). None: no sound, or no project folder."""
    s = song(folder, chosen)
    if s is None:
        return None
    from rostrum_sound import soundtrack
    key = soundtrack.stamp(folder, s["id"]), round(seconds, 6)
    if key not in _BEATS:
        _BEATS.clear()
        _BEATS[key] = list(soundtrack.grid(soundtrack.read(folder, s["id"]), seconds)["beats"])
    return _BEATS[key]
