"""Where a brought-in model lives: inside the project folder, <project>/assets/<source>/<model>/, so the project stays
whole when it is copied or sent. A model already there is reused (no second download). A download is made in a
`.partial` folder and moved into place only when whole, so a cut download never looks like a model.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .net import AssetError

RECORD = ".asset.json"             # what the folder holds: source, model, licence, site, its model file
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def folder_of(project, source_id: str, asset: str) -> Path:
    if not project:
        raise AssetError("this scene is not in a project folder; save it into one first, then bring models in")
    if not ID.match(asset or ""):
        raise AssetError(f'"{asset}" is not a model id (letters, digits, _ . - only)')
    return Path(project) / "assets" / source_id / asset


def already(project, source_id: str, asset: str) -> Path | None:
    """The model file of a model already brought in, or None."""
    folder = folder_of(project, source_id, asset)
    try:
        main = folder / json.loads((folder / RECORD).read_text(encoding="utf-8"))["main"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return main if main.is_file() else None


def bring_in(src, asset: str, project, progress=None) -> Path:
    if (main := already(project, src.id, asset)) is not None:
        return main
    final = folder_of(project, src.id, asset)
    partial = final.with_name(final.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir(parents=True)
    try:
        main = src.fetch(asset, partial, progress)
        rel = main.relative_to(partial).as_posix()
        (partial / RECORD).write_text(json.dumps({"source": src.id, "id": asset, "licence": src.licence,
                                                  "site": src.site, "main": rel}, indent=2), encoding="utf-8")
        shutil.rmtree(final, ignore_errors=True)       # a half-left folder from an older run (no record in it)
        partial.rename(final)
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    return final / rel
