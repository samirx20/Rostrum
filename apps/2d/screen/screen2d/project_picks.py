"""The settings panel's picks that come from outside the document (rows.py control "pick": a list, never a text box to
type an id or a name into): a text's Font (the families the engine can draw, each shown in its own face), the scene's
Soundtrack (the project's Sound items), a 3D render layer's 3D item (the project's rendered 3D items) and its shot."""
from __future__ import annotations

from rostrum2d import render3d, settings
from rostrum_core import project

_faces: list[dict] | None = None


def fonts() -> list[dict]:
    """[{value, label, face}] by name: each family a text can name (settings.font_files), `face` the family Qt draws
    it with (the file registered once with Qt, so the list shows each font in its own face; "" if Qt can't read it)."""
    global _faces
    if _faces is None:
        from PySide6.QtGui import QFontDatabase
        _faces = []
        for family, path in settings.font_files():
            fid = QFontDatabase.addApplicationFont(str(path))
            qt = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
            _faces.append({"value": family, "label": family, "face": qt[0] if qt else ""})
    return _faces


def _items(folder, kind: str) -> list[dict]:
    return [{"value": it["id"], "label": it["name"]} for it in project.items(folder, kind)] if folder else []


def _shots(folder, ref: str) -> list[dict]:
    shots = {r["manifest"].get("source", {}).get("shot") for r in project.renders(folder, ref) if r["kind"] == "pictures"} \
        if folder and ref else set()
    return [{"value": s, "label": s} for s in sorted(s for s in shots if s)]


def choices(item: dict, param: str, folder) -> list[dict] | None:
    """The pick's entries, or None when `param` is not one of these."""
    kind = item.get("type")
    if kind == "text" and param == "font":
        return fonts()
    if kind == "comp" and param == "soundtrack":
        return _items(folder, "sound")
    if kind == "render3d" and param == "item":
        return [{"value": it["id"], "label": it["name"]} for it in render3d.placeable(folder)]
    if kind == "render3d" and param == "shot":
        return _shots(folder, item.get("item", ""))
    return None
