"""The user's own sound folders (a Sonniss bundle, BOOM, Soundly exports, their recordings): a list kept in the user's
settings (`~/.rostrum/settings/sound-library.json`), never in a project. Nothing from these folders is copied
anywhere; the index keeps paths and measurements only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from rostrum_core import RostrumError, codes

FILE = "sound-library.json"


def settings_file() -> Path:
    """Where the list lives. `ROSTRUM_SETTINGS_DIR` moves it (tests)."""
    root = Path(os.environ["ROSTRUM_SETTINGS_DIR"]) if os.environ.get("ROSTRUM_SETTINGS_DIR") else \
        Path.home() / ".rostrum" / "settings"
    return root / FILE


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
    f = settings_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({"folders": items}, indent=1), encoding="utf-8")
    tmp.replace(f)


def add(folder) -> str:
    """Add a folder (absolute, must exist). Adding one already listed changes nothing. Returns its full path."""
    p = Path(folder).expanduser()
    if not p.is_absolute():
        raise RostrumError(codes.BAD_ARGUMENT, "sound library", f'folder "{folder}"', "must be a full path")
    if not p.is_dir():
        raise RostrumError(codes.NOT_FOUND, "sound library", f'folder "{p}"', "is not a folder")
    path = str(p.resolve())
    have = folders()
    if path not in have:
        _write(have + [path])
    return path


def remove(folder) -> bool:
    """Forget a folder (its files are not touched). True when it was listed."""
    path = str(Path(folder).expanduser().resolve())
    have = folders()
    if path not in have:
        return False
    _write([f for f in have if f != path])
    return True
