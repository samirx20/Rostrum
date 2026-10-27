"""The asset library: sources of free (CC0) models a person can bring into a scene (Import › Asset library).

Every source is off until the person switches it on in the sheet (settings.py, the person's settings file); nothing
is asked of a site while its source is off (net.py checks before every request), and an agent can never switch one
on. A model's files are downloaded only when someone brings it in, into the project folder (store.py), so the
project stays whole.

    register(source)                      add a source: the built-ins below and a plugin's go through the same call
    sources() / source(id)                the registered ones, in order / one by id (fails plainly)
    search(id, query, page)               one page of a source's models: [{id, name, thumb_url, ...}]
    bring_in(id, asset, project, progress) download a model into <project>/assets/<source>/<asset>/ (or reuse it): its file

A source is an object with: id, name, licence ("CC0"), site (its web address), what ("CC0 models"),
search(query, page), files(asset) (what a download fetches) and fetch(asset, folder, progress) -> the model file.
base.py's Source gives fetch for sources whose files() lists plain files.
"""
from __future__ import annotations

from pathlib import Path

from . import settings, store
from .net import AssetError

_SOURCES: dict[str, object] = {}


def register(source) -> None:
    for need in ("id", "name", "licence", "site", "search", "files", "fetch"):
        if not hasattr(source, need):
            raise ValueError(f"asset source {getattr(source, 'id', source)!r} has no {need!r}")
    if source.id in _SOURCES:
        raise ValueError(f"asset source {source.id!r} is already registered")
    _SOURCES[source.id] = source


def sources() -> list:
    return list(_SOURCES.values())


def source(source_id: str):
    if source_id not in _SOURCES:
        raise AssetError(f'"{source_id}" is not an asset source; the sources are: {", ".join(_SOURCES) or "none"}.')
    return _SOURCES[source_id]


def facts(src) -> dict:
    """What the sheet and the agents' asset_sources show of a source."""
    return {"id": src.id, "name": src.name, "licence": src.licence, "site": src.site,
            "what": getattr(src, "what", f"{src.licence} models"), "on": settings.is_on(src.id)}


def search(source_id: str, query: str = "", page: int = 0) -> list[dict]:
    src = source(source_id)
    settings.require_on(src)
    return src.search(query.strip(), max(0, int(page)))


def bring_in(source_id: str, asset: str, project, progress=None) -> Path:
    src = source(source_id)
    settings.require_on(src)
    return store.bring_in(src, asset, project, progress)


def _builtins() -> None:
    from .ambientcg import AmbientCG
    from .polyhaven import PolyHaven
    register(PolyHaven())
    register(AmbientCG())


_builtins()

__all__ = ["AssetError", "register", "sources", "source", "facts", "search", "bring_in"]
