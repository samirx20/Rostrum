"""A project's items and their renders, read from the project folder (project-service CONTRACT.md § 1, § 7;
shared/HANDOFFS.md § 1, § 5). The minimal first piece of the project service: enough for one app to list the
others' items and pick a finished render (Sound picking a 2D render as its picture).

An item is a document in `docs/` (its kind from the file's extension) or a row in `project.json`'s "items" (a file
the project keeps in `media/`, added by `add_file`: a brush tip picture, a paper …).
Its renders are the finished version folders `renders/<item>/vNNN/`, each with a `manifest.json`;
`vNNN.partial/` (in progress or failed) is never listed. Writers use begin_render / finish_render.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import filestamps
from .errors import RostrumError, codes
from .project_files import _SAFE_ID, _kept, _kept_read, _read_json, _read_kept
from .project_media import media_file, media_outside, media_place, media_problems, media_ref
from .project_renders import begin_render, finish_render, latest_render, next_render, renders, save_beside

KIND_OF_EXT = {".mtn": "2d", ".trk": "sound", ".trd": "3d", ".rsm": "edit"}


def _doc_name(path: Path, item_id: str) -> str:
    def read(p):
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("doc", {}).get("name") or ""
        except (OSError, ValueError):
            return ""
    return _kept_read(path, read) or item_id


def items(folder, kind: str | None = None) -> list[dict]:
    """Every item of the project: {id, kind, name, file, renders}, sorted by name. `kind` filters ("2d" …)."""
    folder = Path(folder)
    if not folder.is_dir():
        raise RostrumError(codes.NOT_FOUND, "project", str(folder), "is not a project folder")
    found: dict[str, dict] = {}
    for f in sorted((folder / "docs").glob("*")) if (folder / "docs").is_dir() else ():
        if f.suffix in KIND_OF_EXT:
            found[f.stem] = {"id": f.stem, "kind": KIND_OF_EXT[f.suffix], "name": _doc_name(f, f.stem),
                             "file": f"docs/{f.name}"}
    if (folder / "project.json").is_file():
        for row in _read_kept(folder / "project.json", "project").get("items", []):
            found[row["id"]] = {**found.get(row["id"], {}), **{k: row[k] for k in ("id", "kind", "name", "file", "hash")
                                                              if k in row}}
    out = [{**it, "name": it.get("name") or it["id"], "renders": renders(folder, it["id"])} for it in found.values()]
    return sorted((it for it in out if kind is None or it["kind"] == kind), key=lambda it: it["name"].lower())


def item(folder, item_id: str) -> dict:
    every = items(folder)
    for it in every:
        if it["id"] == item_id:
            return it
    raise RostrumError.not_found("project", "item", item_id, [it["id"] for it in every])


def main(folder, kind: str) -> dict | None:
    """The project's main item of a kind (the "main mix" for "sound"): the one marked in project.json's "main", else
    the first of that kind by name; None when the project has none. A mark naming an item that is gone is loud."""
    every = items(folder, kind)
    meta = Path(folder) / "project.json"
    marked = _read_json(meta, "project").get("main", {}).get(kind) if meta.is_file() else None
    if not marked:
        return every[0] if every else None
    for it in every:
        if it["id"] == marked:
            return it
    raise RostrumError(codes.NOT_FOUND, "project", f'main {kind} "{marked}"', f"is not a {kind} item of this project",
                       [it["id"] for it in every], "Pick another item as the main one.")


def set_main(folder, kind: str, item_id: str | None):
    """Mark `item_id` (an item of `kind`) as the project's main one; None clears the mark (the first by name wins).
    project.json is written whole; its other keys stay as they were."""
    if item_id is not None and item_id not in (ids := [it["id"] for it in items(folder, kind)]):
        raise RostrumError(codes.NOT_FOUND, "project", f'{kind} item "{item_id}"', "is not in this project", ids)
    meta = Path(folder) / "project.json"
    data = _read_json(meta, "project") if meta.is_file() else {}
    marks = {k: v for k, v in data.pop("main", {}).items() if k != kind} | ({kind: item_id} if item_id else {})
    from .storage import write_atomic
    write_atomic(meta, json.dumps(data | ({"main": marks} if marks else {}), indent=1, ensure_ascii=False))
    filestamps.forget(meta)


def add_file(folder, kind: str, name: str, source) -> dict:
    """Keep the file `source` in the project as an item of `kind`: copied to `media/<kind>/`, a row in project.json.
    Its id comes from its content (`<kind>_<hash 12>`), so the same picture added twice is one item, and anything
    pointing at the id points at exactly that content. Paths in the row are relative: the project can move."""
    from .cache import file_hash
    from .storage import write_atomic
    source = Path(source)
    if not source.is_file():
        raise RostrumError(codes.NOT_FOUND, "project", str(source), "is not a file")
    if not _SAFE_ID.match(kind):
        raise RostrumError(codes.BAD_ARGUMENT, "project", f'kind "{kind}"', "may use only letters, digits, _ and -")
    digest = file_hash(source)
    row = {"id": f"{kind}_{digest[:12]}", "kind": kind, "name": name or source.stem,
           "file": f"media/{kind}/{digest[:12]}{source.suffix.lower()}", "hash": digest}
    dest = Path(folder) / row["file"]
    if not dest.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    meta = Path(folder) / "project.json"
    data = _read_json(meta, "project") if meta.is_file() else {}
    data["items"] = [r for r in data.get("items", []) if r.get("id") != row["id"]] + [row]
    write_atomic(meta, json.dumps(data, indent=1, ensure_ascii=False))
    filestamps.forget(meta)
    return row


def change_file_item(folder, item_id: str, name: str | None) -> None:
    """Rename a kept file's item (`name`), or remove it (None): its row leaves project.json and its file goes with
    it. An id that is no kept file of this project is loud."""
    from .storage import write_atomic
    meta = Path(folder) / "project.json"
    data = _read_json(meta, "project") if meta.is_file() else {}
    rows = data.get("items", [])
    row = next((r for r in rows if r.get("id") == item_id), None)
    if row is None:
        raise RostrumError.not_found("project", "item", item_id, [r.get("id") for r in rows])
    if name is None:
        data["items"] = [r for r in rows if r is not row]
        (Path(folder) / row["file"]).unlink(missing_ok=True)
    else:
        row["name"] = name
    write_atomic(meta, json.dumps(data, indent=1, ensure_ascii=False))
    filestamps.forget(meta)
