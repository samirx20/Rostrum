"""ambientCG's 3D models (CC0), through its API v3 (https://docs.ambientcg.com/api/v3/assets/):
    /api/v3/assets?type=3d-model&q=<words>&limit=&offset=&include=title,thumbnails    a page of models
    /api/v3/assets?id=<id>&include=downloads                                          its zips (we take a 1K JPG one)
A model comes as one zip; it is unpacked and the model file inside picked (glb, gltf, usd, fbx, obj, in that order).
"""
from __future__ import annotations

import urllib.parse
import zipfile
from pathlib import Path

from . import net
from .net import AssetError
from .base import Source, inside

API = "https://ambientcg.com/api/v3/assets"
PER_PAGE = 40
PREFER = ("SQ-1K-JPG", "LQ-1K-JPG", "1K-JPG")          # the standard model with small textures first
MODEL_EXT = (".glb", ".gltf", ".usdz", ".usdc", ".usd", ".usda", ".fbx", ".obj")


class AmbientCG(Source):
    id, name, site = "ambientcg", "ambientCG", "https://ambientcg.com"

    def search(self, query: str, page: int) -> list[dict]:
        args = {"type": "3d-model", "limit": PER_PAGE, "offset": page * PER_PAGE, "include": "title,thumbnails"}
        if query:
            args["q"] = query
        data = net.get_json(self.id, f"{API}?{urllib.parse.urlencode(args)}")
        return [{"id": a["id"], "name": a.get("title") or a["id"], "thumb_url": (a.get("thumbnails") or {}).get("256-PNG", ""), "by": ""}
                for a in (data or {}).get("assets", []) if a.get("id")]

    def files(self, asset: str) -> dict:
        data = net.get_json(self.id, f"{API}?{urllib.parse.urlencode({'id': asset, 'include': 'downloads'})}")
        found = [a for a in (data or {}).get("assets", []) if a.get("id") == asset]
        zips = [d for d in (found[0].get("downloads") or []) if d.get("extension") == "zip"] if found else []
        if not zips:
            raise AssetError(f'ambientCG has no download of "{asset}"')
        pick = next((d for want in PREFER for d in zips if d.get("attributes", "").endswith(want)), None) \
            or min(zips, key=lambda d: d.get("size") or 0)
        name = urllib.parse.parse_qs(urllib.parse.urlsplit(pick["url"]).query).get("file", [f"{asset}.zip"])[0]
        return {"files": [{"path": name, "url": pick["url"], "size": pick.get("size")}], "main": None, "zip": name}

    def main_of(self, plan: dict, folder: Path) -> Path:
        archive = inside(folder, plan["zip"])
        try:
            with zipfile.ZipFile(archive) as z:
                for member in z.infolist():
                    inside(folder, member.filename)          # nothing may unpack outside the model's folder
                z.extractall(folder)
        except zipfile.BadZipFile:
            raise AssetError(f"ambientCG's download {plan['zip']} is not a whole zip") from None
        archive.unlink()
        models = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in MODEL_EXT]
        if not models:
            raise AssetError(f"ambientCG's {plan['zip']} holds no model file ({', '.join(MODEL_EXT)})")
        return min(models, key=lambda p: (MODEL_EXT.index(p.suffix.lower()), len(p.parts)))
