"""What the layers panel and the keyframe timeline list, from one composition. No Qt.

Both list layers top of the stack first (as they look: the last drawn is on top). The layers panel puts a
layer's effects and masks under it, then a group's own layers; a folded layer hides all of that. The timeline
has one row per layer (all its keys, its effects' and masks' too, as one summary line); an opened layer shows
one row per animated field. A group's layers follow it, indented.
"""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum2d.evaluate import animated, keys_of


def label_of(item: dict, owner: dict | None = None) -> str:
    """A key reads as its layer, field and time ("title · Opacity at 0.9 s"); everything else by its name, or its
    id while the name is only the type's ("Text")."""
    if item.get("type") == "key" and owner is not None:
        p = F.param(owner["type"], item["prop"])
        return f"{label_of(owner)} · {p.label if p else item['prop']} at {item['t']:g} s"
    name = item.get("name")
    return str(item["id"] if not name or name == F.LABELS.get(item.get("type")) else name)


def _owned(layer: dict) -> list[dict]:
    return [*layer.get("effects", []), *layer.get("masks", [])]


def layer_rows(comp: dict, folded: set[str]) -> list[dict]:
    out: list[dict] = []

    def walk(layers, depth):
        for lay in reversed(layers):
            inside = _owned(lay) + lay.get("layers", [])
            out.append({"id": lay["id"], "label": label_of(lay), "kind": lay["type"], "depth": depth,
                        "shape": lay.get("shape", ""), "owned": False,
                        "fold": "" if not inside else ("closed" if lay["id"] in folded else "open"),
                        "animated": bool(lay.get("keys"))})
            if inside and lay["id"] not in folded:
                for o in _owned(lay):
                    out.append({"id": o["id"], "label": label_of(o), "kind": o["type"], "depth": depth + 1,
                                "shape": "", "owned": True, "fold": "", "animated": bool(o.get("keys"))})
                walk(lay.get("layers", []), depth + 1)

    walk(comp.get("layers", []), 0)
    return out


def _fields(layer: dict) -> list[tuple[dict, str]]:
    """(owner, prop) for every animated field of a layer and of its effects and masks, in field-table order."""
    out = []
    for owner in [layer, *_owned(layer)]:
        props = animated(owner)
        out += [(owner, p.name) for p in F.FIELDS[owner["type"]] if p.name in props]
    return out


def _keys(owner: dict, prop: str) -> list[dict]:
    return [{"id": k["id"], "t": k["t"]} for k in keys_of(owner, prop)]


def tracks(comp: dict, opened: set[str]) -> list[dict]:
    out: list[dict] = []

    def walk(layers, depth):
        for lay in reversed(layers):
            fields = _fields(lay)
            summary = sorted((k for o, p in fields for k in _keys(o, p)), key=lambda k: k["t"])
            is_open = lay["id"] in opened and bool(fields)
            out.append({"row": "layer", "id": lay["id"], "label": label_of(lay), "kind": lay["type"],
                        "depth": depth, "fold": "" if not fields else ("open" if is_open else "closed"),
                        "keys": summary, "owner": lay["id"], "prop": ""})
            if is_open:
                for owner, prop in fields:
                    name = F.param(owner["type"], prop).label
                    if owner is not lay:
                        name = f"{label_of(owner)} · {name}"
                    out.append({"row": "field", "id": f"{owner['id']}.{prop}", "label": name, "kind": owner["type"],
                                "depth": depth + 1, "fold": "", "keys": _keys(owner, prop),
                                "owner": owner["id"], "prop": prop})
            walk(lay.get("layers", []), depth + 1)

    walk(comp.get("layers", []), 0)
    return out
