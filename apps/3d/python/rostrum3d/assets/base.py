"""What most asset sources share: fetch() downloads the plain files that files() lists into a folder and hands back
the model file. A source whose download is an archive overrides main_of (ambientcg.py unpacks its zip there).
"""
from __future__ import annotations

from pathlib import Path

from . import net
from .net import AssetError


def inside(folder: Path, rel: str) -> Path:
    """`folder / rel`, refused when a site's file name would land outside the folder ("../x", an absolute path)."""
    path = (folder / rel).resolve()
    if not path.is_relative_to(folder.resolve()):
        raise AssetError(f'the site named a file outside its model\'s folder ("{rel}"), so nothing was kept')
    return path


class Source:
    id = name = site = ""
    licence = "CC0"
    what = "CC0 models"

    def search(self, query: str, page: int) -> list[dict]:
        raise NotImplementedError

    def files(self, asset: str) -> dict:
        """{"files": [{"path": relative path, "url", "size"}], "main": the model file's relative path (or None)}."""
        raise NotImplementedError

    def fetch(self, asset: str, folder: Path, progress=None) -> Path:
        plan = self.files(asset)
        total, got = max(1, sum(f.get("size") or 0 for f in plan["files"])), 0

        def tick(n):
            nonlocal got
            got += n
            if progress:
                progress(min(1.0, got / total))
        for f in plan["files"]:
            net.download(self.id, f["url"], inside(folder, f["path"]), tick)
        return self.main_of(plan, folder)

    def main_of(self, plan: dict, folder: Path) -> Path:
        main = inside(folder, plan["main"])
        if not main.is_file():
            raise AssetError(f"{self.name} sent no model file ({plan['main']} is missing)")
        return main
