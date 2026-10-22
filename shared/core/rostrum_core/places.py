"""Reopen at the same place (INTERACTION.md 1.19): where the person left each project, kept in their home, never in
the document. It is screen state: no change, no history, no undo, and an agent never reads or moves it.

    <userhome>/places/<app>.json    {"<folder>|<item>": {"at": clock time, "place": {...}}}, newest KEEP kept

A place is a plain dict the app fills: scene, selection (ids), playhead (seconds), range, zoom / pan (canvasview.place()),
the time view (start, span) ... whatever it can put back. A scripted run's home is its scratch one (userhome), so tests
and checks never touch the person's places.

    save(app, folder, item, place)         remember it (two windows at once never lose each other's)
    load(app, folder, item)                the place, or {}
    keep_existing(place, exists)           what still stands: a scene / layer that was deleted is dropped quietly, one
                                           item at a time, and the rest of the place stays
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from . import userhome
from .storage import write_atomic

KEEP = 60
ID_KEYS = ("scene", "focus_item")                 # one id each: dropped when it no longer exists
ID_LISTS = ("selection",)                         # lists of ids: filtered, the ones that exist stay


def file(app: str) -> Path:
    return userhome.home() / "places" / f"{app}.json"


def _key(folder, item) -> str:
    return f"{Path(folder).resolve()}|{item}"


def _read(app: str) -> dict:
    try:
        data = json.loads(file(app).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}                                 # no places yet, or a damaged file: the person just starts at the top


def save(app: str, folder, item: str, place: dict) -> None:
    with userhome.locked(file(app), "places"):
        data = _read(app)
        data[_key(folder, item)] = {"at": time.time(), "place": place}
        newest = sorted(data.items(), key=lambda kv: -kv[1].get("at", 0))[:KEEP]
        write_atomic(file(app), json.dumps(dict(newest), indent=1, ensure_ascii=False))


def load(app: str, folder, item: str) -> dict:
    place = _read(app).get(_key(folder, item), {}).get("place")
    return place if isinstance(place, dict) else {}


def keep_existing(place: dict, exists) -> dict:
    """`place` without what no longer stands: `exists(id) -> bool` is the document's own lookup."""
    out = dict(place)
    for k in ID_KEYS:
        if k in out and not exists(out[k]):
            del out[k]
    for k in ID_LISTS:
        if k in out:
            out[k] = [i for i in out[k] if exists(i)]
    return out
