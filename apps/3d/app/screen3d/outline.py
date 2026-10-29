"""What the scene list and its keys show, from one 3D document. No Qt.

Scene list (the bottom panel's left column, SPEC §1): the item tree (a group's or import's children indented under it,
an import's parts and a mesh's bone chain too; the arrow folds them; a combine is a group with the Combine icon, and in a Subtract every
child after the first, a cutter, has `cutter` set: the row shows a minus before its name), each row with its material's name, dim. The keys sit on the same rows
(scene_rows): all of an item's keys on its own line; the selected item (or the owner of the selected key) opens into
one row per animated field, so its keys can be picked and dragged one by one. An item's line carries what the kit's
LayerTrack.qml draws (rostrum_gui/anim_rows.py): a slim bar from its first key to its last, its animations' stretches
(3D's names: rostrum3d/anims.py, Position / Turn / Scale each one), and, where two of its animations overlap in time,
a second line under it (only while it is opened). Materials and shots are not rows here: the header's Materials chip
and the shot crumb list them (materials(), shots()).
"""
from __future__ import annotations

from rostrum_core.keys import keys_of, layers as anim_layers
from rostrum_gui import anim_rows
from rostrum3d import fields as F
from rostrum3d.anims import animations


def label_of(item: dict, owner: dict | None = None) -> str:
    """A key reads as its item, field and time ("cam · X at 1.5 s"); everything else by its name, or its id while
    the name is only the type's ("Mesh")."""
    if item.get("type") == "key" and owner is not None:
        p = F.param(owner["type"], item["prop"])
        return f"{label_of(owner)} · {p.label if p else item['prop']} at {item['t']:g} s"
    name = item.get("name")
    if item.get("type") == "effector" and (not name or name == F.LABELS["effector"]):
        return f'{str(item.get("kind", "scale")).capitalize()} near {item.get("near") or "its copies"}'   # follows Changes
    return str(item["id"] if not name or name == F.LABELS.get(item.get("type")) else name)


def _row(item: dict, depth: int, fold: str = "", row: str = "item") -> dict:
    return {"row": row, "id": item["id"], "label": label_of(item), "kind": item["type"], "depth": depth, "fold": fold,
            "animated": bool(item.get("keys")), "material": item.get("material", ""),
            "sim": item.get("simulate", "off") if row in ("item", "layer") else "off"}     # a body's badge (Falls / Stays still)


def named(data: dict, key: str) -> list[dict]:
    """The document's materials or shots, for the header's chip and crumb: [{value: id, label: name}]."""
    return [{"value": m["id"], "label": label_of(m)} for m in data.get(key, [])]


def _animated(item: dict, layer: str = "") -> list[str]:
    return [p.name for p in F.FIELDS.get(item["type"], ())
            if any(k["prop"] == p.name and (k.get("layer") or "") == layer for k in item.get("keys", []))]


def _summary(keys: list[dict], fps: float) -> list[dict]:
    """An item's own line: keys of several settings at one frame are ONE diamond (`ids`: every key it stands for)."""
    by: dict[int, dict] = {}
    for k in sorted(keys, key=lambda k: k["t"]):
        f = round(k["t"] * fps)
        by.setdefault(f, {**k, "ids": []})["ids"].append(k["id"])
    return list(by.values())


def scene_rows(data: dict, folded: set[str], opened: str, fps: float = 24, layer: str = "") -> list[dict]:
    """The scene list with its keys on the same rows (the kit's LayerTrack rowData): {row "layer"|"part"|"field", id,
    owner, label, kind, depth, fold, material (its name), keys, stretches, bar, start, end}. `opened`: the item whose
    animated fields (and second lines) get rows of their own. `layer`: the timeline's chosen animation layer, whose
    keys alone show ("" = the Base; a layer's keys have no stretches)."""
    mats = {m["id"]: label_of(m) for m in data.get("materials", [])}
    out: list[dict] = []

    def add(it, depth, fold="", row="layer", cutter=False):
        props, anims = _animated(it, layer), [] if layer else animations(it)
        is_open = it["id"] == opened
        later = [a for a in anims if a["line"] > 0] if is_open else []      # folded: one line holds every key
        elsewhere = {k["id"] for a in later for k in a["keys"]}
        keys = _summary([k for p in props for k in _keys(it, p, layer) if k["id"] not in elsewhere], fps)
        times = [k["t"] for k in keys]
        out.append({**_row(it, depth, fold, row), "owner": it["id"], "keys": keys, "cutter": cutter,
                    "material": mats.get(it.get("material", ""), ""), "bar": len(times) > 1,
                    "start": min(times, default=0), "end": max(times, default=0),
                    "stretches": anim_rows.stretches(it["id"], [a for a in anims if a["line"] == 0 or not is_open])})
        for n in sorted({a["line"] for a in later}):         # overlapping animations: a line each (SPEC §9)
            mine = [a for a in later if a["line"] == n]
            out.append({**_row(it, depth + 1, "", "field"), "id": f"{it['id']}#line{n}", "owner": it["id"], "line": True,
                        "label": ", ".join(a["label"] for a in mine), "kind": "", "material": "",
                        "keys": sorted((k for a in mine for p in a["props"] for k in _keys(it, p)), key=lambda k: k["t"]),
                        "stretches": anim_rows.stretches(it["id"], mine)})
        if is_open:
            out.extend({"row": "field", "id": f"{it['id']}.{p}", "owner": it["id"], "label": F.param(it["type"], p).label,
                        "kind": "", "depth": depth + 1, "fold": "", "material": "", "animated": True,
                        "keys": _keys(it, p, layer), "prop": p} for p in props)

    def walk(items, depth, cutters=False):
        for n, it in enumerate(items):
            inside = it.get("children", []) + it.get("bones", []) + it.get("parts", [])    # a mesh's bones: its chain
            add(it, depth, "" if not inside else ("closed" if it["id"] in folded else "open"), cutter=cutters and n > 0)
            if inside and it["id"] not in folded:
                walk(it.get("children", []) + it.get("bones", []), depth + 1, it.get("type") == "combine" and it.get("op", "subtract") == "subtract")
                for p in it.get("parts", []):
                    add(p, depth + 1, row="part")

    walk(data.get("items", []), 0)
    return out


def scene_items(data: dict):
    stack = list(reversed(data.get("items", [])))
    while stack:
        it = stack.pop()
        yield it
        stack.extend(reversed(it.get("children", []) + it.get("bones", [])))


def _keys(owner: dict, prop: str, layer: str = "") -> list[dict]:
    keys = anim_layers.layer_keys(owner, prop, layer) if layer else keys_of(owner, prop)
    return [{"id": k["id"], "ids": [k["id"]], "t": k["t"]} for k in keys]
