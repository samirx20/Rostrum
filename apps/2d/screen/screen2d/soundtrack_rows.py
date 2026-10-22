"""Scene settings › Soundtrack in the inspector: a choice among the project's RostrumSound items by name (empty = the
project's main mix, project_sound.py), never a bare id to type; absent when the project has no Sound item (nothing
greyed out). The pick is the scene's `soundtrack` field (comp.set, the agents' operation too). No Qt."""
from __future__ import annotations

from rostrum_core import project
from rostrum2d import project_sound


def rows(rows: list[dict], item: dict | None, folder) -> list[dict]:
    if not item or item.get("type") != "comp":
        return rows
    songs = project.items(folder, "sound") if folder else []
    if not songs:
        return [r for r in rows if not (r["row"] == "param" and r["id"] == "soundtrack")]
    try:
        main = project_sound.main_mix(folder)["name"]
    except Exception:  # noqa: BLE001  a stale main mark: the Sound row says it loudly (soundtrack.py); here a plain label
        main = "missing, pick one"
    options = [{"value": "", "label": f"Main mix: {main}"}]
    options += [{"value": s["id"], "label": s["name"]} for s in songs]
    return [{**r, "type": "choice", "options": options, "min": None, "max": None, "unit": ""}
            if r["row"] == "param" and r["id"] == "soundtrack" else r for r in rows]
