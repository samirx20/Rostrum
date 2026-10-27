"""File › Add a song from RostrumSound…: a song made in its own Sound project, copied into this 2D project, where the
Sound row finds it by itself (project_sound.song). A hand maker copied `song.trk` in Explorer, with no way in the app
(critic 2d-final B9). The song's whole state goes: its file, and beside it its history and script (storage_text.paths):
the file alone may be up to 20 changes behind its history. The original stays where it was; nothing is overwritten."""
from __future__ import annotations

import shutil
from pathlib import Path

from rostrum_core.storage_text import paths

SONG_EXT = ".trk"


def add(project, song_file) -> str:
    """Copy the song into `project`; returns the sentence for the top bar. Fails loudly (ValueError, in words)."""
    if not project:
        raise ValueError("this project is not in a project folder yet, so it can't hold a song: open or make a project first (File › New).")
    src, project = Path(song_file), Path(project)
    if src.suffix != SONG_EXT or not src.is_file():
        raise ValueError(f'"{src.name}" is not a RostrumSound song (a {SONG_EXT} file in a Sound project\'s docs folder).')
    item = src.stem
    mine, theirs = paths(project, item, SONG_EXT), paths(src.parent.parent, item, SONG_EXT)
    if src.resolve() == mine["doc"].resolve():
        raise ValueError(f'"{item}" is already this project\'s song.')
    if mine["doc"].exists():
        raise ValueError(f'This project already has a song named "{item}": rename one of them in RostrumSound first.')
    for part, to in mine.items():
        got = src if part == "doc" else theirs[part]
        if got.is_file():
            to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(got, to)
    return f'Added the song "{item}" from RostrumSound: it plays with the picture (the ♪ row).'
