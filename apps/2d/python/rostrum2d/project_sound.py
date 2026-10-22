"""Which of the project's sound plays with a scene: the one answer for the screen's Sound row, inspect_soundtrack, the
inspector's Soundtrack choice and an MP4 export's sound (AGENTS.md rule 9; the sound itself is RostrumSound's).

The scene's `soundtrack` field names a Sound item; empty = the project's main mix (rostrum_core.project.main: the
item marked main in project.json, else the first Sound item by name). No Qt.
"""
from __future__ import annotations

from pathlib import Path

from rostrum_core import project


def main_mix(folder) -> dict | None:
    """The project's main mix ({id, name, file}), or None when the project has no Sound item (a stale mark is loud)."""
    return project.main(folder, "sound") if folder else None


_FOUND: dict = {}       # (folder, chosen) -> (the sound files' stamp, the song): asked on every change, even a pen move


def song(folder, chosen: str = "") -> dict | None:
    """The Sound item that plays: `chosen` (a scene's `soundtrack`) when set, else the main mix; None: no sound.
    Finding it reads every document of the project (their names), so the answer is kept until a Sound file,
    project.json or a Sound item's renders change on disk (`_stamp`)."""
    if not folder:
        return None
    key, stamp = (str(folder), chosen), _stamp(folder)
    got = _FOUND.get(key)
    if got is not None and got[0] == stamp:
        return got[1]
    from rostrum_sound import soundtrack
    if chosen:
        found = soundtrack.find(folder, chosen)
    else:
        m = main_mix(folder)
        found = soundtrack.find(folder, m["id"]) if m else None
    _FOUND[key] = (stamp, found)
    return found


def _stamp(folder) -> tuple:
    """(name, modified, size) of each Sound file in docs/, project.json and each Sound item's renders folder."""
    f = Path(folder)
    sounds = sorted(p for p in (f / "docs").glob("*") if project.KIND_OF_EXT.get(p.suffix) == "sound") \
        if (f / "docs").is_dir() else []
    return tuple((str(p), *_seen(p)) for p in [*sounds, f / "project.json", *(f / "renders" / s.stem for s in sounds)])


def _seen(p: Path) -> tuple[int, int]:
    try:
        st = p.stat()
    except OSError:
        return 0, -1
    return st.st_mtime_ns, st.st_size


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


_SONGS: dict = {}       # (folder, item) -> the song's live Document: one copy per process (cues, video sound, Undo)


def open_song(folder, item: str):
    """The song `item` as a live Document (rostrum_core.live: every change locked, caught up and saved at once; one
    door with Sound's own window). One copy per process, caught up on each call, so 2D's cues, the video sound and the
    screen's Undo all see the same history. Its check reads the project's shared markers ("#Logo · sound")."""
    from rostrum_core import live
    from rostrum_sound.doc import markers as song_markers
    from rostrum_sound.opening import open_whole
    song_markers.use_project(folder)                 # this process works in this project (Undo checks the song too)
    key = (str(folder), item)
    doc = _SONGS.get(key)
    if doc is None:
        doc = _SONGS[key] = open_whole(folder, item)
        live.keep(doc)
    else:
        doc.live.catch_up()
    return doc


_BEATS: dict = {}     # (song's stamp, seconds) -> beat times: describe() runs on every edit, the song's file rarely changes


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
