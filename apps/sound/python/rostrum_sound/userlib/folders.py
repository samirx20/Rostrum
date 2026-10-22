"""The user's own sound folders (a Sonniss bundle, BOOM, Soundly exports, their recordings): a list kept in the user's
settings (`<settings dir>/sound-library.json`), never in a project. Nothing from these folders is copied
anywhere; the index keeps paths and measurements only.
"""
from __future__ import annotations

import json
from pathlib import Path

from rostrum_core import RostrumError, codes, userhome
from rostrum_core.storage import write_atomic

from .. import settings

FILE = "sound-library.json"


def settings_file() -> Path:
    """Where the list lives: the settings folder (settings.settings_dir; `ROSTRUM_SETTINGS_DIR` moves it)."""
    return settings.settings_dir() / FILE


def folders() -> list[str]:
    """The folders, in the order they were added."""
    f = settings_file()
    if not f.is_file():
        return []
    try:
        return list(json.loads(f.read_text(encoding="utf-8")).get("folders", []))
    except ValueError as e:
        raise RostrumError(codes.BAD_ARGUMENT, "sound library", str(f), f"is not readable JSON ({e})",
                           hint="Fix or delete the file; it only lists your sound folders.") from e


def _write(items: list[str]):
    write_atomic(settings_file(), json.dumps({"folders": items}, indent=1))


def add(folder) -> str:
    """Add a folder (absolute, must exist). Adding one already listed changes nothing. Returns its full path."""
    p = Path(folder).expanduser()
    if not p.is_absolute():
        raise RostrumError(codes.BAD_ARGUMENT, "sound library", f'folder "{folder}"', "must be a full path")
    if not p.is_dir():
        raise RostrumError(codes.NOT_FOUND, "sound library", f'folder "{p}"', "is not a folder")
    path = str(p.resolve())
    with userhome.locked(settings_file()):
        have = folders()
        if path not in have:
            _write(have + [path])
    return path


def remove(folder) -> bool:
    """Forget a folder (its files are not touched). True when it was listed."""
    path = str(Path(folder).expanduser().resolve())
    with userhome.locked(settings_file()):
        have = folders()
        if path not in have:
            return False
        _write([f for f in have if f != path])
    return True
