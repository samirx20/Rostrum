"""The light scene a clay's grid is built from (ops_pose): one shot's clays, the groups they sit in and its camera, at
its first frame and without bones. The joint finder, Step look and Shape look read a clay's rest shape and nothing else,
so the whole scene (describe: every item at every frame, bones weighed) was worked out only to be replaced by the
look's own scene a moment later (Hello: 0.26 s a describe, two per finding). None (describe it whole) when a clay sits
in anything but a group.
"""
from __future__ import annotations

from . import compile as C, material_scene, shot_layer

THROUGH = ("group",)                      # holders a clay may sit in for this scene; others: the whole describe


def describe_clays(data: dict, shot_id: str, folder=None) -> dict | None:
    info = C.shot_info(data, shot_id)
    shot = C._shot(data, shot_id)
    data = shot_layer.lay(data, shot_id)
    first = range(info["start"], info["start"] + 1)
    fr = C._Frames(data, first, info["fps"], folder)
    fr.shot_camera, fr.shot_size = info["camera"], [info["width"], info["height"]]
    fr.no_skin = True                     # the grid measures the clay at rest
    keep = {info["camera"]}
    items = _kept(data.get("items", []), fr, keep)
    if items is None:
        return None
    return {
        "format": C.FORMAT, "version": C.VERSION,
        "shot": {"id": info["id"], "fps": info["fps"], "start": info["start"], "end": info["start"],
                 "shutter": C.shutter_frames(shot)},
        "world": {"background": C.linear(shot["background"]), "environment": None},
        "materials": material_scene.materials(data, first, info["fps"], folder, C._out),
        "items": items,
    }


def _holds(item: dict, keep: set) -> bool:
    return item["type"] == "clay" or item["id"] in keep or any(_holds(c, keep) for c in item.get("children", []))


def _kept(items: list, fr, keep: set) -> list | None:
    out = []
    for it in items:
        if not _holds(it, keep):
            continue
        if it["type"] == "clay" or it["id"] in keep and not it.get("children"):
            out.append(C._node(it, fr))
        elif it["type"] in THROUGH:
            kids = _kept(it.get("children", []), fr, keep)
            if kids is None:
                return None
            node = C._node({**it, "children": []}, fr)
            node["children"] = kids
            out.append(node)
        else:
            return None
    return out
