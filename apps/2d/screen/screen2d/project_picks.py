"""The settings panel's picks that come from outside the document (rows.py control "pick": a list, never a text box to
type an id or a name into): a text's Font (the families the engine can draw, each shown in its own face), the scene's
Soundtrack (the project's Sound items), a 3D render layer's 3D item (the project's rendered 3D items) and its shot.
And a picture's or video's File row at rest: the name the file came in with (`with_file_names`)."""
from __future__ import annotations

import json
from pathlib import Path

from rostrum2d import fontlist, render3d, settings
from rostrum_core import project

_faces: list[dict] | None = None
SECTIONS = {"shipped": "In Rostrum", "installed": "On this computer"}


def _qt_face(family: str, files: list[str], known: set[str]) -> str:
    """The family Qt draws this one's name with: its own name when Qt knows it (an installed font), else its first
    (upright) file added to Qt (the app's shipped fonts; only that one, so the name shows upright); "" if Qt can't read it."""
    from PySide6.QtGui import QFontDatabase
    if family in known:
        return family
    fid = QFontDatabase.addApplicationFont(files[0]) if files else -1
    names = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
    return names[0] if names else ""


def fonts() -> list[dict]:
    """[{value, label, face, section}]: each family a text can name (rostrum2d/fontlist.py, the engine's one list), the
    app's own first, then the computer's; `face` the family Qt draws its name in, so the list shows each in its face."""
    global _faces
    if _faces is None:
        from PySide6.QtGui import QFontDatabase
        known = set(QFontDatabase.families())
        _faces = [{"value": f["family"], "label": f["family"], "section": SECTIONS.get(f["source"], ""),
                   "face": _qt_face(f["family"], f["files"], known)}
                  for f in fontlist.families()]
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


_names: tuple = (None, 0.0, {})      # (project.json, its time, {file: "pic.png"}): read again only when it changes


def file_name(folder, src: str) -> str:
    """What a picture's or video's File row says at rest: the name the file came in with ("pic.png"), not the store's
    content-named copy ("media/image/ed2d1ea4….png"); "" for a file the project doesn't keep (the row shows its own name)."""
    global _names
    meta = Path(folder) / "project.json" if folder else None
    if not src or meta is None or not meta.is_file():
        return ""
    when = meta.stat().st_mtime
    if _names[0] != meta or _names[1] != when:
        rows = json.loads(meta.read_text(encoding="utf-8")).get("items", [])
        _names = (meta, when, {r["file"]: (r.get("name") or Path(r["file"]).stem) + Path(r["file"]).suffix
                               for r in rows if r.get("file")})
    return _names[2].get(src, "")


def with_file_names(rows: list[dict], item: dict | None, folder) -> list[dict]:
    """The File row of a picture or video says the file's own name at rest (its `words` for its value)."""
    if not item or item.get("type") not in ("image", "video"):
        return rows
    for r in rows:
        if r.get("row") == "param" and r.get("id") == "src" and r.get("value"):
            name = file_name(folder, r["value"])
            if name:
                r["words"] = [{"value": r["value"], "label": name}]
    return rows
