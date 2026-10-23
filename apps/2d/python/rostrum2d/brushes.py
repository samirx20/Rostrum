"""My brushes (painting design §2.1 step 6, §4, P6): a saved brush is an item of kind "brush" — a small JSON file kept
with rostrum_core.project.add_file (media/brush/, a row in project.json, its id from its content) — in one or both
of two places: the **project** (it moves with the project; people and agents share it) and the person's own
**library** (userhome.home()/library, laid out like a project, so it is there in every project; a scripted run gets
a scratch one). The file holds the brush's own identity next to its settings, so two brushes can share settings and
still be two brushes; the same brush in both places is the same file, so the same id, listed once. Files saved before
the identity (H56: the settings alone) still load. A loaded tip or paper is named by its picture's item id (also
content), so keeping a brush somewhere copies its pictures there too. Colour and seed are never saved.

    saved(folder)                          [{id, name, settings, where}], by name; where ⊆ ["project", "library"]
    save(folder, name, values, where=None) a new brush (default: in both, or the library alone with no project)
    duplicate(folder, id)                  a new brush with the same settings, "<name> copy", in the same places
    keep(folder, id, place) / drop(folder, id, place)    add it to / take it out of one place
    rename(folder, id, name) / remove(folder, id)        everywhere it is
    use(folder, id)                        the brush, its pictures copied into the project first (ready to paint)
    for_stroke(settings)                   the settings paint.stroke takes (only those that apply, as it insists)

The same calls serve the screen (brush panel) and agents (mcp/brush_tool.py). No Qt.
"""
from __future__ import annotations

import contextlib
import json
import tempfile
import uuid
from pathlib import Path

from rostrum_core import project, userhome
from rostrum_core.conditions import holds
from rostrum_core.errors import RostrumError, codes

KIND = "brush"
UNSAVED = ("color", "seed")
PLACES = ("project", "library")
PICTURES = {"texture": "tip", "paper": "paper"}       # the settings that may name a loaded picture, and as what


def library() -> Path:
    """The person's own library folder (a scratch one in a scripted run: userhome)."""
    d = userhome.home() / "library"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _roots(folder) -> dict:
    return {"project": Path(folder), "library": library()} if folder else {"library": library()}


def _root(folder, place: str) -> Path:
    roots = _roots(folder)
    if place not in roots:
        raise RostrumError(codes.BAD_ARGUMENT, "brush", f'place "{place}"', "isn't open: no project is" if place ==
                           "project" else "is no place for a brush", list(roots), hint="Save the document first.")
    return roots[place]


def _writing(root: Path):
    """The library is shared by every Rostrum window: its project.json changes under a lock."""
    return userhome.locked(root / "project.json", "brush library") if root == library() else contextlib.nullcontext()


def _name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise RostrumError(codes.BAD_ARGUMENT, "brush", "name", "is empty", hint="Give the brush a name.")
    return name


def _read(root: Path, it: dict) -> dict:
    try:
        data = json.loads((root / it["file"]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RostrumError(codes.CHECK_FAILED, "brush", f'"{it["name"]}" ({it["id"]})', f"can't be read: {e}") from e
    return data["settings"] if "settings" in data else data          # H56 files: the settings alone


def saved(folder) -> list[dict]:
    """Every saved brush, by name: {id, name, settings, where}. A brush in both places is listed once (the project's
    name first). A brush file that is missing or unreadable is loud (never a silently shorter list)."""
    out: dict[str, dict] = {}
    for place, root in _roots(folder).items():
        for it in project.items(root, KIND):
            b = out.setdefault(it["id"], {"id": it["id"], "name": it["name"], "settings": _read(root, it), "where": []})
            b["where"].append(place)
    return sorted(out.values(), key=lambda b: b["name"].lower())


def get(folder, brush_id: str) -> dict:
    every = saved(folder)
    for b in every:
        if b["id"] == brush_id:
            return b
    raise RostrumError.not_found("brush", "saved brush", brush_id, [b["id"] for b in every])


def _row(folder, b: dict) -> tuple[Path, dict]:
    root = _root(folder, b["where"][0])
    return root, next(it for it in project.items(root, KIND) if it["id"] == b["id"])


def _bring(folder, settings: dict, dest: Path) -> None:
    """Copy the loaded pictures `settings` names into `dest` (from the project or the library); built-in ones need
    nothing. A picture found in neither is loud."""
    from rostrum_paint import library as pics, pictures
    for key, as_ in PICTURES.items():
        v = settings.get(key)
        if not v or v in (pictures.TEXTURES if as_ == "tip" else pictures.PAPERS):
            continue
        if any(it["id"] == v for it in project.items(dest, pics.KIND[as_])):
            continue
        found = [(r, it) for r in _roots(folder).values() for it in project.items(r, pics.KIND[as_]) if it["id"] == v]
        if not found:
            raise RostrumError(codes.NOT_FOUND, "brush", f'{as_} picture "{v}"', "is in neither the project nor your "
                               "library", hint="Load the picture again on Edit brush, then save the brush.")
        src, it = found[0]
        with _writing(dest):
            project.add_file(dest, pics.KIND[as_], it["name"], src / it["file"])
    if folder and dest == Path(folder):
        pics.use_project(folder)                         # the project's tip / paper choices grow


def _add(folder, place: str, name: str, file: Path, settings: dict) -> dict:
    dest = _root(folder, place)
    _bring(folder, settings, dest)
    with _writing(dest):
        return project.add_file(dest, KIND, name, file)


def save(folder, name: str, values: dict, where=None) -> dict:
    """Keep `values` (the brush's settings; colour and seed left out) as a new brush named `name`, in `where`
    (default: the project and the library; the library alone when no project is open)."""
    from rostrum_paint import BRUSH
    by = {p.name: p for p in BRUSH}
    unknown = sorted(set(values) - set(by))
    if unknown:
        raise RostrumError(codes.BAD_ARGUMENT, "brush", ", ".join(unknown), "are no brush settings", sorted(by))
    settings = {k: by[k].check(v, f"brush {k}") for k, v in sorted(values.items()) if k not in UNSAVED}
    where = list(where or _roots(folder))
    name = _name(name)
    with tempfile.TemporaryDirectory(prefix="rostrum-brush-") as tmp:
        f = Path(tmp) / "brush.json"
        f.write_text(json.dumps({"brush": uuid.uuid4().hex, "settings": settings}, indent=1), encoding="utf-8")
        rows = [_add(folder, place, name, f, settings) for place in where]
    return {"id": rows[0]["id"], "name": name, "settings": settings, "where": where}


def duplicate(folder, brush_id: str) -> dict:
    b = get(folder, brush_id)
    return save(folder, f'{b["name"]} copy', b["settings"], b["where"])


def keep(folder, brush_id: str, place: str) -> None:
    b = get(folder, brush_id)
    if place not in b["where"]:
        root, it = _row(folder, b)
        _add(folder, place, b["name"], root / it["file"], b["settings"])


def drop(folder, brush_id: str, place: str) -> None:
    b = get(folder, brush_id)
    if place in b["where"]:
        root = _root(folder, place)
        with _writing(root):
            project.change_file_item(root, brush_id, None)


def rename(folder, brush_id: str, name: str) -> None:
    name = _name(name)
    for place in get(folder, brush_id)["where"]:
        root = _root(folder, place)
        with _writing(root):
            project.change_file_item(root, brush_id, name)


def remove(folder, brush_id: str) -> None:
    for place in get(folder, brush_id)["where"]:
        drop(folder, brush_id, place)


def use(folder, brush_id: str) -> dict:
    """The brush, ready to paint in the open project: a loaded tip or paper it names is copied in from the library."""
    b = get(folder, brush_id)
    if folder:
        _bring(folder, b["settings"], Path(folder))
    return b


def for_stroke(settings: dict) -> dict:
    """A saved brush's settings as paint.stroke's arguments: those that apply now (a tip angle only when the tip
    does not turn with the stroke …), judged by each setting's own rule (`valid_when`)."""
    from rostrum_paint import BRUSH
    return {p.name: settings[p.name] for p in BRUSH if p.name in settings and holds(p.valid_when, settings)}
