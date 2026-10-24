"""Scene settings › Soundtrack in the inspector: a pick among the project's RostrumSound items by name (the field's
control "pick": project_picks.py lists them, and with no Sound item the row and its "+ Sound" are absent). Here only
the empty choice gets the main mix's name: "Main mix: <its name>" (project_sound.py). No Qt."""
from __future__ import annotations

from rostrum2d import project_sound


def rows(rows: list[dict], item: dict | None, folder) -> list[dict]:
    if not item or item.get("type") != "comp" or not any(r["row"] == "param" and r["id"] == "soundtrack" and r.get("holds", True) for r in rows):
        return rows
    try:
        main = project_sound.main_mix(folder)["name"]
    except Exception:  # noqa: BLE001  a stale main mark: the Sound row says it loudly (soundtrack.py); here a plain label
        main = "missing, pick one"
    named = lambda o: {**o, "label": f"Main mix: {main}"} if o["value"] == "" else o      # noqa: E731
    return [{**r, "options": [named(o) for o in r["options"]]} if r["row"] == "param" and r["id"] == "soundtrack" else r
            for r in rows]
