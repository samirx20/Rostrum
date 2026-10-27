"""The songs' own markers (`marker()` in a Sound script, Sound's marker.add) as the rest of the project sees them:
read-only context, {name: seconds} on the scene's clock (a song plays from the scene's 0 s), read through Sound's
read-only API like the voice lines (lipsync/voice.py). One marker namespace (AGENTS.md rule 8): 2D's look_frame,
timing and export find a song's marker by name like a project marker. Before this they were invisible to 2D, and
adding the same names as project markers made the song "damaged" at the end of an export (2D final critic, F7-2).

The rule for a name that is both a project marker and a song's own marker:
- at the same time (within a millisecond): it is one marker, nothing to do;
- at different times: refused when the second one is made (project markers: markers.edit; Sound: its marker ops),
  and an export checks it before drawing a frame (`check`). Where it still happens (two files edited apart), the
  project marker's time is the one read, and `conflicts` names it.

Cheap to call often: the song list is re-read when the docs folder or project.json changed, a song when its file or
its history changed (filestamps: kept between a screen's ticks).
"""
from __future__ import annotations

from pathlib import Path

from . import filestamps
from .errors import RostrumError, codes

SAME_S = 1e-3
_SONGS: dict = {}       # folder -> (stamp of docs folder + project.json, [(item id, name, (doc path, history path))])
_READ: dict = {}        # (folder, item id) -> (stamp, {name: seconds})
_BUSY: set = set()      # folders being read now: reading a song asks the project's markers again (not its songs)


def _songs(folder) -> list:
    base = Path(folder)
    key = (filestamps.stamp(base / "docs"), filestamps.stamp(base / "project.json"))
    got = _SONGS.get(str(folder))
    if got is None or got[0] != key:
        from . import project
        from .storage import paths
        try:
            items = project.items(folder, "sound")
        except RostrumError:
            items = []
        rows = [(it["id"], it["name"], (base / it["file"], paths(folder, it["id"], ".trk")["history"]))
                for it in items if it.get("file")]
        got = _SONGS[str(folder)] = (key, rows)
    return got[1]


def _read(folder, item_id, files) -> dict[str, float]:
    stamp = tuple(filestamps.stamp(f) for f in files)
    got = _READ.get((str(folder), item_id))
    if got is None or got[0] != stamp:
        from rostrum_sound import soundtrack
        from rostrum_sound.doc import markers as song
        root = soundtrack.read(folder, item_id)
        try:
            with song.project(None):        # its own markers as written (a clash with a project marker is `check`'s)
                own = dict(song.all(root, own=True))
        except RostrumError:
            with song.project(folder):      # one placed on a project marker ("#drop+2beats") needs the project's
                own = dict(song.all(root, own=True))
        got = _READ[(str(folder), item_id)] = (stamp, own)
    return got[1]


def times(folder) -> dict[str, float]:
    """{name: seconds} of every song's own markers in the project ({} without songs, or without RostrumSound)."""
    if folder is None:
        return {}
    songs = _songs(folder)
    if not songs:
        return {}
    try:
        import rostrum_sound  # noqa: F401
    except ImportError:
        return {}
    if str(folder) in _BUSY:
        return {}
    out: dict[str, float] = {}
    _BUSY.add(str(folder))
    try:
        for item_id, _, files in songs:
            out.update(_read(folder, item_id, files))
    finally:
        _BUSY.discard(str(folder))
    return out


def stamp(folder) -> tuple:
    """A value that changes when any song's markers may have changed (the song list, a song's file or history)."""
    if folder is None:
        return ()
    return tuple((i, *(filestamps.stamp(f) for f in files)) for i, _, files in _songs(folder))


def listing(folder) -> list[dict]:
    """[{name, at, item, song}] of every song's own markers, by time: the ruler's read-only flags."""
    if folder is None or not _songs(folder):
        return []
    try:
        import rostrum_sound  # noqa: F401
    except ImportError:
        return []
    out = []
    for item_id, name, files in _songs(folder):
        out += [{"name": n, "at": t, "item": item_id, "song": name} for n, t in _read(folder, item_id, files).items()]
    return sorted(out, key=lambda m: m["at"])


def conflicts(project_times: dict[str, float], song_times: dict[str, float]) -> list[tuple[str, float, float]]:
    """[(name, project seconds, song seconds)] for names in both at different times (case and outer spaces ignored)."""
    from .marker_times import lookup
    out = []
    for n, t in song_times.items():
        p = lookup(project_times, n)
        if p is not None and abs(p - t) > SAME_S:
            out.append((n, p, t))
    return out


def refuse(name: str, at: float, song_times: dict[str, float], where: str) -> None:
    """Making project marker `name` at `at` s: refused when a song has its own marker of that name elsewhere."""
    clash = conflicts({name: at}, song_times)
    if clash:
        n, _, t = clash[0]
        raise RostrumError(codes.BAD_ARGUMENT, where, f'marker "{name}" at {at:g} s',
                           f"a song already has its own marker \"{n}\" at {t:g} s (one name is one marker)",
                           hint=f"Use {t:g} s (the same marker), another name, or move the song's marker in RostrumSound.")


def check(folder, project_times: dict[str, float], where: str) -> None:
    """Before an export draws a frame: a name at two different times is a loud error now, not after the frames."""
    clash = conflicts(project_times, times(folder))
    if clash:
        n, p, t = clash[0]
        raise RostrumError(codes.CHECK_FAILED, where, f'marker "{n}"', f"is a project marker at {p:g} s and a song's "
                           f"own marker at {t:g} s", [c[0] for c in clash],
                           hint="Move one onto the other's time (then they are one marker) or rename one.")
