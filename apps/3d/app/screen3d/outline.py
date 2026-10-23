"""What the scene list and its keys show, from one 3D document. No Qt.

Scene list (the bottom panel's left column, SPEC §1): the item tree (a group's or import's children indented under it,
an import's parts too; the arrow folds them; a combine is a group with the Combine icon, and in a Subtract every
child after the first, a cutter, has `cutter` set: the row shows a minus before its name), each row with its material's name, dim. The keys sit on the same rows
(scene_rows): all of an item's keys on its own line; the selected item (or the owner of the selected key) opens into
one row per animated field, so its keys can be picked and dragged one by one. Materials and shots are not rows here:
the header's Materials chip and the shot crumb list them (materials(), shots()).
"""
from __future__ import annotations

from rostrum_core.keys import keys_of
from rostrum3d import fields as F


def label_of(item: dict, owner: dict | None = None) -> str:
    """A key reads as its item, field and time ("cam · X at 1.5 s"); everything else by its name, or its id while
    the name is only the type's ("Mesh")."""
    if item.get("type") == "key" and owner is not None:
        p = F.param(owner["type"], item["prop"])
        return f"{label_of(owner)} · {p.label if p else item['prop']} at {item['t']:g} s"
    name = item.get("name")
    return str(item["id"] if not name or name == F.LABELS.get(item.get("type")) else name)


def _row(item: dict, depth: int, fold: str = "", row: str = "item") -> dict:
    return {"row": row, "id": item["id"], "label": label_of(item), "kind": item["type"], "depth": depth, "fold": fold,
            "animated": bool(item.get("keys")), "material": item.get("material", "")}


def named(data: dict, key: str) -> list[dict]:
    """The document's materials or shots, for the header's chip and crumb: [{value: id, label: name}]."""
    return [{"value": m["id"], "label": label_of(m)} for m in data.get(key, [])]


def _animated(item: dict) -> list[str]:
    return [p.name for p in F.FIELDS.get(item["type"], ()) if any(k["prop"] == p.name for k in item.get("keys", []))]


def scene_rows(data: dict, folded: set[str], opened: str) -> list[dict]:
    """The scene list with its keys on the same rows (kit KeyRows' model): {row "layer"|"part"|"field", id, owner,
    label, kind, depth, fold, material (its name), keys}. `opened`: the item whose animated fields get rows of their own."""
    mats = {m["id"]: label_of(m) for m in data.get("materials", [])}
    out: list[dict] = []

    def add(it, depth, fold="", row="layer", cutter=False):
        props = _animated(it)
        keys = list({k["t"]: k for k in sorted((k for p in props for k in _keys(it, p)), key=lambda k: -k["t"])}.values())[::-1]
        # (one diamond per time on the item's own line: two fields keyed at once share it; their rows split them)
        out.append({**_row(it, depth, fold, row), "owner": it["id"], "keys": keys, "cutter": cutter,
                    "material": mats.get(it.get("material", ""), "")})
        if it["id"] == opened:
            out.extend({"row": "field", "id": f"{it['id']}.{p}", "owner": it["id"], "label": F.param(it["type"], p).label,
                        "kind": "", "depth": depth + 1, "fold": "", "material": "", "animated": True,
                        "keys": _keys(it, p), "prop": p} for p in props)

    def walk(items, depth, cutters=False):
        for n, it in enumerate(items):
            inside = it.get("children", []) + it.get("parts", [])
            add(it, depth, "" if not inside else ("closed" if it["id"] in folded else "open"), cutter=cutters and n > 0)
            if inside and it["id"] not in folded:
                walk(it.get("children", []), depth + 1, it.get("type") == "combine" and it.get("op", "subtract") == "subtract")
                for p in it.get("parts", []):
                    add(p, depth + 1, row="part")

    walk(data.get("items", []), 0)
    return out


def scene_items(data: dict):
    stack = list(reversed(data.get("items", [])))
    while stack:
        it = stack.pop()
        yield it
        stack.extend(reversed(it.get("children", [])))


def _keys(owner: dict, prop: str) -> list[dict]:
    return [{"id": k["id"], "t": k["t"]} for k in keys_of(owner, prop)]
