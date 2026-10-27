"""Model thumbnails, fetched only when a tile shows (and only while its source is on), kept in the user cache folder
(<settings home>/cache/asset-thumbs/<source>/<model>.png) so a second look costs nothing.
"""
from __future__ import annotations

from pathlib import Path

from rostrum_core import userhome

from . import net
from .store import ID


def cached(source_id: str, asset: str) -> Path:
    return userhome.home() / "cache" / "asset-thumbs" / source_id / f"{asset}.png"


def fetch(source_id: str, asset: str, url: str) -> Path | None:
    """The thumbnail file (downloaded once); None when the model has none."""
    if not url or not ID.match(asset):
        return None
    path = cached(source_id, asset)
    if not path.is_file():
        net.download(source_id, url, path)
    return path
