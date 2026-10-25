"""The project's main mix: the one song the other apps play with the picture (2D's soundtrack, the Editor's final mix).
A mark in project.json (`rostrum_core.project.set_main`, built in H32); this is Sound's one door to it, used by the
`run_set_main_mix` tool and the screen's "Make this the main mix".

    is_main(folder, "song")     # True when this song is the main mix (the first by name counts until one is marked)
    make_main(folder, "song")   # marks it; loud when the item is not a sound item of the project
"""
from __future__ import annotations

from pathlib import Path

from rostrum_core import filestamps, project

_known: dict = {}       # (folder, item id) -> (the stamps of project.json and docs/, the answer)


def is_main(folder, item_id: str) -> bool:
    """Kept while project.json and the docs folder are as they were (filestamps): the screen asks on every selection,
    and the answer reads every song file of the project (~4 ms a click on a 3-minute song)."""
    if not folder:
        return False
    stamps = (filestamps.stamp(Path(folder) / "project.json"), filestamps.stamp(Path(folder) / "docs"))
    kept = _known.get((str(folder), item_id))
    if kept is not None and kept[0] == stamps and None not in stamps[1:]:
        return kept[1]
    m = project.main(folder, "sound")
    _known[(str(folder), item_id)] = (stamps, bool(m) and m["id"] == item_id)
    return _known[(str(folder), item_id)][1]


def count(folder) -> int:
    return len(project.items(folder, "sound")) if folder else 0


def make_main(folder, item_id: str) -> dict:
    """Mark `item_id` as the main mix. Answers {item, name, was} (the item that was the main mix before)."""
    was = project.main(folder, "sound")
    project.set_main(folder, "sound", item_id)
    _known.clear()
    now = project.main(folder, "sound")
    return {"item": now["id"], "name": now["name"], "was": was["id"] if was else None}
