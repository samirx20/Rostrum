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
import re
import shutil
from pathlib import Path

from .errors import RostrumError, codes

KIND_OF_EXT = {".mtn": "2d", ".trk": "sound", ".trd": "3d", ".rsm": "edit"}
_VERSION = re.compile(r"^v(\d{3,})$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def _read_json(path: Path, where: str) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RostrumError(codes.CHECK_FAILED, where, str(path), f"can't be read: {e}") from e


def _doc_name(path: Path, item_id: str) -> str:
    try:
        doc = json.loads(path.read_text(encoding="utf-8")).get("doc", {})
    except (OSError, ValueError):
        return item_id
    return doc.get("name") or item_id


def renders(folder, item_id: str) -> list[dict]:
    """Finished renders of one item, newest first: {version, kind, path, files, manifest}."""
    base = Path(folder) / "renders" / item_id
    out = []
    for d in base.iterdir() if base.is_dir() else ():
        m = _VERSION.match(d.name)
        if not m or not d.is_dir() or not (d / "manifest.json").is_file():
            continue
        manifest = _read_json(d / "manifest.json", f"render {item_id}/{d.name}")
        out.append({"version": int(m.group(1)), "kind": manifest.get("kind", ""), "path": str(d),
                    "files": sorted(p.name for p in d.iterdir() if p.name != "manifest.json"), "manifest": manifest})
    return sorted(out, key=lambda r: -r["version"])


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
        for row in _read_json(folder / "project.json", "project").get("items", []):
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
    return row


def media_ref(folder, path) -> str:
    """How a document stores the file `path`: relative to the project folder (forward slashes) when it lies inside
    it, so the project can be copied or moved; else the path as given (a file the person keeps elsewhere)."""
    try:
        return Path(path).resolve().relative_to(Path(folder).resolve()).as_posix()
    except (ValueError, OSError):
        return str(path)


def media_place(folder, value: str) -> str | None:
    """The place IN the project (relative) that a stored absolute path stands for, or None to leave it as it is: a file
    inside the folder, or one an older copy of the project still names from the folder it was copied FROM (the same
    place under `media/` here, and the old file is gone or the same size). A relative path or a file kept elsewhere: None."""
    p = Path(value)
    if not p.is_absolute():
        return None
    rel = media_ref(folder, p)
    if rel != str(p):
        return rel
    parts = p.parts
    if "media" not in parts:
        return None
    tail = Path(*parts[len(parts) - 1 - parts[::-1].index("media"):])
    here = Path(folder) / tail
    if here.is_file() and (not p.is_file() or p.stat().st_size == here.stat().st_size):
        return tail.as_posix()
    return None


def media_outside(folder, value: str) -> bool:
    """True for an absolute path to a file the project does not hold (it will not travel with the project)."""
    return bool(folder) and bool(value) and Path(value).is_absolute() and media_ref(folder, value) == value


def media_file(folder, value) -> Path:
    """The file a stored reference (`media_ref`) points to: an absolute path as it is, a relative one under the
    project folder (no folder: relative to the process, as a path always was)."""
    p = Path(value)
    return p if p.is_absolute() or folder is None else Path(folder) / p


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


def latest_render(folder, item_id: str, kind: str | None = None) -> dict | None:
    """The newest finished render of an item ("pictures" / "sound" to pick one kind), or None."""
    return next((r for r in renders(folder, item_id) if kind is None or r["kind"] == kind), None)


def begin_render(folder, item_id: str) -> Path:
    """A new, empty `renders/<item>/vNNN.partial/` (the next version number) for a render to write into."""
    if not _SAFE_ID.match(item_id):
        raise RostrumError(codes.BAD_ARGUMENT, "render", f'item "{item_id}"', "may use only letters, digits, _ and -")
    base = Path(folder) / "renders" / item_id
    base.mkdir(parents=True, exist_ok=True)
    taken = [int(m.group(1)) for d in base.iterdir() if (m := re.match(r"^v(\d{3,})(\.partial)?$", d.name))]
    part = base / f"v{max(taken, default=0) + 1:03d}.partial"
    part.mkdir()
    return part


def finish_render(partial: Path, manifest: dict) -> Path:
    """Write the manifest and rename `vNNN.partial/` to `vNNN/`. A render with no files is refused (loud)."""
    partial = Path(partial)
    if not partial.name.endswith(".partial") or not partial.is_dir():
        raise RostrumError(codes.BAD_ARGUMENT, "render", str(partial), "is not a vNNN.partial folder")
    if not any(p.name != "manifest.json" for p in partial.iterdir()):
        raise RostrumError(codes.JOB_FAILED, "render", str(partial), "has no files: nothing was rendered")
    (partial / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    done = partial.with_name(partial.name[:-len(".partial")])
    partial.rename(done)
    return done



def save_beside(folder, item_id: str, render_dir, dest) -> Path:
    """Copy the project a render came from to `dest` (next to a render copied out of the project), so another app
    can open the film as a project: project.json, docs/, data/, media/, colour/, .rostrum/ and this render's
    version folder only (other items' renders and exports stay behind). Written whole: `dest.partial`, then
    renamed; an older copy at `dest` is replaced."""
    folder, render_dir, dest = Path(folder), Path(render_dir), Path(dest)
    if not (folder / "docs").is_dir():
        raise RostrumError(codes.NOT_FOUND, "render", str(folder), "is not a project folder (no docs/)")
    part = dest.with_name(dest.name + ".partial")
    shutil.rmtree(part, ignore_errors=True)
    for name in ("docs", "data", "media", "colour", ".rostrum"):
        if (folder / name).is_dir():
            shutil.copytree(folder / name, part / name, ignore=shutil.ignore_patterns("*.partial", "*.lock"))
    for name in ("project.json",):
        if (folder / name).is_file():
            shutil.copy2(folder / name, part / name)
    shutil.copytree(render_dir, part / "renders" / item_id / render_dir.name)
    if dest.exists():
        shutil.rmtree(dest)
    part.rename(dest)
    return dest
