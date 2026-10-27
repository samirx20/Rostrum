"""Which asset sources are on: the person's own choice, kept in their settings folder (assets.json; a scripted run
reads and writes its scratch home through userhome, never the person's). Every source is off until the person
switches it on in the sheet; agents only read this (their tools have no way to switch a source on).
"""
from __future__ import annotations

import json

from rostrum_core import userhome

from .net import AssetError

FILE = "assets.json"


def _path():
    return userhome.home() / FILE


def _read() -> dict:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def is_on(source_id: str) -> bool:
    return (_read().get("on") or {}).get(source_id) is True


def set_on(source_id: str, on: bool) -> None:
    """The person's switch in the sheet (assets_qt.py): the only caller."""
    path = _path()
    with userhome.locked(path, "asset library settings"):
        data = _read()
        data.setdefault("on", {})[source_id] = bool(on)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def require_on(src) -> None:
    """Fail plainly when a source is off (a source object, or its id)."""
    source_id = getattr(src, "id", src)
    if not is_on(source_id):
        name = getattr(src, "name", None) or _name_of(source_id)
        raise AssetError(f"{name} is off; the person switches it on in Import › Asset library.", off=True)


def _name_of(source_id: str) -> str:
    from . import _SOURCES                 # (late: the package imports this module)
    return getattr(_SOURCES.get(source_id), "name", source_id)
