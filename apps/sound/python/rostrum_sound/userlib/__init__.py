"""Bring your own sound library: the user's own sound folders, indexed once (content-keyed, in the shared cache),
cut into single sounds, measured (kind, length, attack, brightness, loudness) and searched by kind and shape.
Nothing from these folders is copied into a project or the app; the index keeps paths and measurements only.

    from rostrum_sound import userlib
    userlib.add_folder(r"D:\\Sounds\\Sonniss GDC 2024")       # listed in ~/.rostrum/settings, indexed now
    userlib.search(kind="whoosh", length="short", brightness="bright")
"""
from __future__ import annotations

from . import folders, index
from .folders import folders as list_folders
from .search import closest, library, search, sound_id


def add_folder(folder, cache_dir=None, progress=None) -> dict:
    """List a folder in the user's settings and index it (from the cache when unchanged). Returns the index."""
    return index.index_folder(folders.add(folder), cache_dir, progress)


__all__ = ["add_folder", "closest", "library", "list_folders", "search", "sound_id"]
