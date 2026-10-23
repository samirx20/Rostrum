"""My brushes (painting design §2.1 step 6, §4): a saved brush is a project item of kind "brush" — a small JSON file
of brush settings kept in the project (rostrum_core.project.add_file: media/brush/, a row in project.json, its id
from its content), so people and agents share them and they move with the project. A loaded tip or paper is named by
its own project item id, so it comes along as it is. Colour and seed are never saved (the colour is the person's).

    saved(folder)               [{id, name, settings}], by name
    save(folder, name, values)  keep these settings as a brush; its row (the same settings twice = one brush, renamed)
    rename(folder, id, name) / remove(folder, id)
    for_stroke(settings)        the settings paint.stroke takes (only those that apply, as it insists)

The same calls serve the screen (brush panel) and agents (mcp/brush_tool.py). No Qt.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from rostrum_core import project
from rostrum_core.conditions import holds
from rostrum_core.errors import RostrumError, codes

KIND = "brush"
UNSAVED = ("color", "seed")


def _need(folder, what: str):
    if not folder:
        raise RostrumError(codes.BAD_ARGUMENT, "brush", what, "needs a project to keep brushes in: this document "
                           "isn't saved in one yet", hint="Save it first.")


def _name(name: str) -> str:
    name = (name or "").strip()
    if not name:
        raise RostrumError(codes.BAD_ARGUMENT, "brush", "name", "is empty", hint="Give the brush a name.")
    return name


def saved(folder) -> list[dict]:
    """The project's saved brushes, by name: {id, name, settings}. A brush file that is missing or unreadable is
    loud (never a silently shorter list)."""
    out = []
    for it in project.items(folder, KIND) if folder else ():
        path = Path(folder) / it["file"]
        try:
            settings = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise RostrumError(codes.CHECK_FAILED, "brush", f'"{it["name"]}" ({it["id"]})', f"can't be read: {e}") from e
        out.append({"id": it["id"], "name": it["name"], "settings": settings})
    return out


def get(folder, brush_id: str) -> dict:
    every = saved(folder)
    for b in every:
        if b["id"] == brush_id:
            return b
    raise RostrumError.not_found("brush", "saved brush", brush_id, [b["id"] for b in every])


def save(folder, name: str, values: dict) -> dict:
    """Keep `values` (the brush's settings; colour and seed left out) in the project as a brush named `name`."""
    _need(folder, "Save this brush")
    from rostrum_paint import BRUSH
    by = {p.name: p for p in BRUSH}
    unknown = sorted(set(values) - set(by))
    if unknown:
        raise RostrumError(codes.BAD_ARGUMENT, "brush", ", ".join(unknown), "are no brush settings", sorted(by))
    settings = {k: by[k].check(v, f"brush {k}") for k, v in sorted(values.items()) if k not in UNSAVED}
    with tempfile.TemporaryDirectory(prefix="rostrum-brush-") as tmp:
        f = Path(tmp) / "brush.json"
        f.write_text(json.dumps(settings, indent=1), encoding="utf-8")
        row = project.add_file(folder, KIND, _name(name), f)
    return {"id": row["id"], "name": row["name"], "settings": settings}


def rename(folder, brush_id: str, name: str) -> None:
    _need(folder, "Rename")
    get(folder, brush_id)
    project.change_file_item(folder, brush_id, _name(name))


def remove(folder, brush_id: str) -> None:
    _need(folder, "Delete")
    get(folder, brush_id)
    project.change_file_item(folder, brush_id, None)


def for_stroke(settings: dict) -> dict:
    """A saved brush's settings as paint.stroke's arguments: those that apply now (a tip angle only when the tip
    does not turn with the stroke …), judged by each setting's own rule (`valid_when`)."""
    from rostrum_paint import BRUSH
    return {p.name: settings[p.name] for p in BRUSH if p.name in settings and holds(p.valid_when, settings)}
