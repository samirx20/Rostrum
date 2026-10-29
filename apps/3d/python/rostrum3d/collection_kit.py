"""Collections (PR1): a named set of items that lights, material assigns and hide / show can target at once.

    doc ─ collections ─ collection {id, type, name, items: [item ids], material: "" | a material id}

Its members are the items it lists plus, when `material` is set, every item using that material (a rule: a chrome
prop added later joins by itself). A listed item that was deleted is skipped. A light's `lightsOnly` may name a
collection: the compiler sends its members (shot_layer.lay), so the core never sees a collection.
"""
from __future__ import annotations

from rostrum_core.tree import walk

LIST = "collections"
TYPE = "collection"
USERS = ("mesh", "combine", "import", "part", "clay")      # what names a material (ops_scene.USERS)


def all_of(data: dict) -> list[dict]:
    return data.get(LIST) or []


def ids(data: dict) -> set[str]:
    return {c["id"] for c in all_of(data)}


def _items(data: dict, items=None):
    stack = list(items if items is not None else data.get("items", []))
    while stack:
        it = stack.pop()
        yield it
        stack += it.get("children", []) + it.get("parts", [])


def members(data: dict, coll: dict, items=None) -> list[str]:
    """The collection's items, listed first (in order), then those its material rule finds; each once."""
    every = {it["id"]: it for it in _items(data, items)}
    out = [i for i in coll.get("items", []) if i in every]
    if mat := coll.get("material"):
        out += sorted(i for i, it in every.items() if it.get("type") in USERS and it.get("material") == mat)
    return list(dict.fromkeys(out))


def has_links(data: dict) -> bool:
    """A light's linking names a collection (the compiler then expands it)."""
    names = ids(data)
    return bool(names) and any(it.get("type") == "light" and names & set(it.get("lightsOnly", "").split())
                               for it in _items(data))


def expand_links(data: dict, items: list[dict]) -> list[dict]:
    """`items` with every light's `lightsOnly` naming collections turned into their members' ids."""
    by_id = {c["id"]: c for c in all_of(data)}

    def one(it):
        if it.get("type") == "light" and any(n in by_id for n in it.get("lightsOnly", "").split()):
            named = []
            for n in it["lightsOnly"].split():
                named += members(data, by_id[n], items) if n in by_id else [n]
            it = {**it, "lightsOnly": " ".join(dict.fromkeys(m for m in named if m != it["id"]))}
        if it.get("children"):
            it = {**it, "children": [one(c) for c in it["children"]]}
        return it
    return [one(i) for i in items]


def problems(data: dict, lists: dict) -> list[str]:
    """The document check's part: a collection's material is a real material; ids don't clash with items."""
    out = []
    mats = {m["id"] for m in walk(data, lists) if m.get("type") == "material"}
    for c in all_of(data):
        if c.get("material") and c["material"] not in mats:
            out.append(f'collection {c["id"]}.material: no material "{c["material"]}"')
        if not isinstance(c.get("items", []), list):
            out.append(f'collection {c["id"]}.items: is a list of item ids')
    return out


def label(c: dict) -> str:
    return c.get("name") or c["id"]

