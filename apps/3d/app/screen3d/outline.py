"""What the outliner and the timeline list, from one 3D document. No Qt.

Outliner: three short sections. Scene: the item tree (a group's or import's children indented under it, an import's
parts too; the arrow folds them). Materials and Shots: one row each. Every row selects its thing.
Timeline: one summary row per animated item (all its keys on one line); the selected item (or the owner of the
selected key) opens into one row per animated field, so its keys can be picked and dragged one by one.
"""
from __future__ import annotations

from rostrum2d.evaluate import keys_of
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


def outliner_rows(data: dict, folded: set[str]) -> list[dict]:
    out: list[dict] = [{"row": "section", "id": "section:scene", "label": "Scene", "kind": "", "depth": 0, "fold": "",
                        "animated": False, "material": ""}]

    def walk(items, depth):
        for it in items:
            inside = it.get("children", []) + it.get("parts", [])
            out.append(_row(it, depth, "" if not inside else ("closed" if it["id"] in folded else "open")))
            if inside and it["id"] not in folded:
                walk(it.get("children", []), depth + 1)
                out.extend(_row(p, depth + 1, row="part") for p in it.get("parts", []))

    walk(data.get("items", []), 0)
    for key, title in (("materials", "Materials"), ("shots", "Shots")):
        if data.get(key):
            out.append({"row": "section", "id": f"section:{key}", "label": title, "kind": "", "depth": 0, "fold": "",
                        "animated": False, "material": ""})
            out.extend(_row(m, 0) for m in data[key])
    return out


def scene_items(data: dict):
    stack = list(reversed(data.get("items", [])))
    while stack:
        it = stack.pop()
        yield it
        stack.extend(reversed(it.get("children", [])))


def _keys(owner: dict, prop: str) -> list[dict]:
    return [{"id": k["id"], "t": k["t"]} for k in keys_of(owner, prop)]


def tracks(data: dict, opened: str) -> list[dict]:
    """Rows for the timeline. `opened`: the item whose fields get their own rows ("" for none)."""
    out: list[dict] = []
    for it in scene_items(data):
        props = [p.name for p in F.FIELDS[it["type"]] if any(k["prop"] == p.name for k in it.get("keys", []))]
        if not props and it["id"] != opened:
            continue
        summary = sorted((k for p in props for k in _keys(it, p)), key=lambda k: k["t"])
        out.append({"row": "item", "id": it["id"], "label": label_of(it), "keys": summary, "owner": it["id"], "prop": ""})
        if it["id"] == opened:
            out += [{"row": "field", "id": f"{it['id']}.{p}", "label": F.param(it["type"], p).label,
                     "keys": _keys(it, p), "owner": it["id"], "prop": p} for p in props]
    return out
