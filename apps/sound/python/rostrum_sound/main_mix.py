"""The project's main mix: the one song the other apps play with the picture (2D's soundtrack, the Editor's final mix).
A mark in project.json (`rostrum_core.project.set_main`, built in H32); this is Sound's one door to it, used by the
`run_set_main_mix` tool and the screen's "Make this the main mix".

    is_main(folder, "song")     # True when this song is the main mix (the first by name counts until one is marked)
    make_main(folder, "song")   # marks it; loud when the item is not a sound item of the project
"""
from __future__ import annotations

from rostrum_core import project


def is_main(folder, item_id: str) -> bool:
    m = project.main(folder, "sound") if folder else None
    return bool(m) and m["id"] == item_id


def count(folder) -> int:
    return len(project.items(folder, "sound")) if folder else 0


def make_main(folder, item_id: str) -> dict:
    """Mark `item_id` as the main mix. Answers {item, name, was} (the item that was the main mix before)."""
    was = project.main(folder, "sound")
    project.set_main(folder, "sound", item_id)
    now = project.main(folder, "sound")
    return {"item": now["id"], "name": now["name"], "was": was["id"] if was else None}
