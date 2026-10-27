"""Poly Haven's models (CC0), through its public API (https://api.polyhaven.com):
    /assets?t=models    every model with its name, tags and categories (one list; searched here, cached per run)
    /files/<id>         the files of each format and size: we take the glTF at 1k with its textures ("include")
Thumbnails: https://cdn.polyhaven.com/asset_img/thumbs/<id>.png?width=256
"""
from __future__ import annotations

import urllib.parse

from . import net
from .net import AssetError
from .base import Source

API = "https://api.polyhaven.com"
THUMB = "https://cdn.polyhaven.com/asset_img/thumbs/{}.png?width=256"
PER_PAGE = 40
SIZES = ("1k", "2k", "4k")          # the smallest set there is


class PolyHaven(Source):
    id, name, site = "polyhaven", "Poly Haven", "https://polyhaven.com/models"

    def __init__(self):
        self._all: list[dict] | None = None

    def _models(self) -> list[dict]:
        if self._all is None:
            data = net.get_json(self.id, f"{API}/assets?t=models")
            if not isinstance(data, dict):
                raise AssetError("api.polyhaven.com sent no list of models")
            models = [{"id": k, "name": v.get("name") or k, "thumb_url": THUMB.format(urllib.parse.quote(k)),
                       "by": ", ".join(v.get("authors") or {}), "date": v.get("date_published") or 0,
                       "words": " ".join([k, v.get("name") or "", *v.get("tags", []), *v.get("categories", [])]).lower()}
                      for k, v in data.items() if isinstance(v, dict)]
            self._all = sorted(models, key=lambda m: -m["date"])        # newest first, as the site shows them
        return self._all

    def search(self, query: str, page: int) -> list[dict]:
        words = query.lower().split()
        found = [m for m in self._models() if all(w in m["words"] for w in words)]
        return [{k: m[k] for k in ("id", "name", "thumb_url", "by")} for m in found[page * PER_PAGE:(page + 1) * PER_PAGE]]

    def files(self, asset: str) -> dict:
        data = net.get_json(self.id, f"{API}/files/{urllib.parse.quote(asset)}")
        sets = (data or {}).get("gltf") or {}
        size = next((s for s in SIZES if s in sets), None)
        if size is None:
            raise AssetError(f'Poly Haven has no glTF of "{asset}"')
        gltf = sets[size]["gltf"]
        main = urllib.parse.urlsplit(gltf["url"]).path.rsplit("/", 1)[-1]
        files = [{"path": main, "url": gltf["url"], "size": gltf.get("size")}]
        files += [{"path": rel, "url": f["url"], "size": f.get("size")} for rel, f in (gltf.get("include") or {}).items()]
        return {"files": files, "main": main}
