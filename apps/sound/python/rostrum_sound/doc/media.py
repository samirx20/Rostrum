"""Where a clip's file is: the ONE place a clip's `media` becomes a file on disk.

A take recorded into the project (and any file the project holds) is stored RELATIVE to the project folder
(`media/Recording-take-1.wav`), so copying or moving the folder keeps every take working. A file that lives outside
the project stays the absolute path it was given. `file(value)` turns either into the path to open: a relative one
is joined to the project this process works in (markers.use_project / markers.project). A relative one with no
project is a loud error: it is never read against the folder the process was started from (a desktop shortcut starts
elsewhere), so every process that reads takes (the screen, an agent server, the clean-up job) names its project.

`upgrade` (DocKind.upgrade, on open) converts an older song's absolute takes: one inside the song's own folder, or
one that points into the folder this song was copied FROM (same name under media/ here, and the old file is gone or
the same size). Files that genuinely live elsewhere are left alone.
"""
from __future__ import annotations

import copy
import shutil
from contextlib import contextmanager
from pathlib import Path

from rostrum_core import RostrumError, codes, project as P

from . import markers


def file(value) -> str:
    """The path to open for a clip's `media` (relative: under the project folder; no project: a loud error)."""
    folder = markers._PROJECT[0]
    if folder is None and not Path(value).is_absolute():
        raise RostrumError(codes.NOT_FOUND, "media", f'"{value}"', "is a place in a project, but no project folder is open",
                           hint="Open the song from its project folder (an absolute path is read as it is).")
    return str(P.media_file(folder, value))


@contextmanager
def of(doc):
    """Resolve clip files against this document's project folder for a block (no folder: leave things as they are)."""
    folder = getattr(doc, "folder", None)
    if folder is None:
        yield
    else:
        with markers.project(folder):
            yield


def keep(folder, source) -> str:
    """What a clip stores for a file brought INTO the song: the file is copied to the project's `media/` folder (a
    same-named different file gets "-2", "-3" …; the same file twice is one copy) and the stored path is relative,
    so the song travels with it. No project folder: the path as given."""
    from rostrum_core.cache import file_hash
    source = Path(source)
    if folder is None or P.media_ref(folder, source) != str(source):
        return P.media_ref(folder, source) if folder else str(source)           # already inside the project
    media = Path(folder) / "media"
    media.mkdir(parents=True, exist_ok=True)
    dest, n = media / source.name, 1
    while dest.exists() and file_hash(dest) != file_hash(source):
        n += 1
        dest = media / f"{source.stem}-{n}{source.suffix}"
    if not dest.exists():
        shutil.copyfile(source, dest)
    return P.media_ref(folder, dest)


def exists(path) -> bool:
    return Path(path).is_file()


def upgrade(data: dict, lists: dict, folder=None):
    """Older songs' absolute takes made relative: (new data, label) or None when nothing changes."""
    if folder is None:
        return None
    new, n = copy.deepcopy(data), 0
    for track in new.get("tracks", []):
        for clip in track.get("clips", []):
            m = clip.get("media")
            rel = P.media_place(folder, m) if isinstance(m, str) else None
            if rel:
                clip["media"], n = rel, n + 1
    return (new, f"{n} recorded take{'s' if n != 1 else ''} made relative to the project") if n else None


def tidy(calls: list[dict], folder=None) -> list[dict]:
    """A full path typed by hand (a person, an agent) inside the song's folder is stored as a place in it, like a
    recorded take. A path outside stays as given."""
    if folder is None:
        return calls

    def fix(v):
        if isinstance(v, dict):
            return {k: (_place(folder, x) if k == "media" else fix(x)) for k, x in v.items()}
        return [fix(x) for x in v] if isinstance(v, list) else v
    return [{**c, "args": fix(c["args"])} for c in calls]


def _place(folder, value):
    return P.media_ref(folder, value) if isinstance(value, str) and Path(value).is_absolute() else value
