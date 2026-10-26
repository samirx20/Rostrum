"""Reading a project's JSON files, kept per file stamp (see project.py)."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from . import filestamps
from .errors import RostrumError, codes

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


_kept: dict = {}        # str(path) -> (its stamp, what was read from it): read again only when the file changed


def _kept_read(path: Path, read):
    """`read(path)`, kept per file stamp (filestamps): a screen listing the project on every pick (a scene's Soundtrack
    pick) parsed every document whole each time, so a pick cost more the bigger the documents."""
    when = filestamps.stamp(path)
    got = _kept.get(str(path))
    if when is not None and got is not None and got[0] == when:
        return got[1]
    out = read(path)
    if when is not None:
        _kept[str(path)] = (when, out)
    return out


def _read_json(path: Path, where: str) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RostrumError(codes.CHECK_FAILED, where, str(path), f"can't be read: {e}") from e


def _read_kept(path: Path, where: str) -> dict:
    """_read_json kept per file stamp, for listing only: the caller gets its own copy (it may change it)."""
    return copy.deepcopy(_kept_read(path, lambda p: _read_json(p, where)))
