"""Finding items in any app's document. Each document kind says where its lists of child items live
(`lists = {"doc": ["layers"], "group": ["children"]}`); that table is all the shared code needs to find, diff
and merge any app's tree (OPERATIONS.md § 2). Every item is a dict with "id" and "type"; the root's id is "root".
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Loc:
    item: dict
    parent: str | None     # parent item id (None for the root)
    key: str | None        # the list on the parent that holds it
    index: int | None


def child_keys(item: dict, lists: dict) -> list[str]:
    return lists.get(item.get("type"), [])


def index(data: dict, lists: dict) -> dict[str, Loc]:
    """id -> where it is. Raises ValueError on a duplicate id: one id, one item."""
    out = {data["id"]: Loc(data, None, None, None)}
    stack = [data]
    while stack:
        item = stack.pop()
        for key in child_keys(item, lists):
            for i, child in enumerate(item.get(key, [])):
                if child["id"] in out:
                    raise ValueError(f"two items have the id {child['id']!r}")
                out[child["id"]] = Loc(child, item["id"], key, i)
                stack.append(child)
    return out


class View:
    """A read-only look at a whole document, handed to a kind's facts(item, doc): an item's parent, or any item by
    id (a note's valid_when can ask about its track's instrument). The index is built once, on first use."""

    def __init__(self, data: dict, lists: dict, idx: dict[str, Loc] | None = None):
        self.data, self.lists, self._idx = data, lists, idx

    def locs(self) -> dict[str, Loc]:
        if self._idx is None:
            self._idx = index(self.data, self.lists)
        return self._idx

    def item(self, id_) -> dict | None:
        loc = self.locs().get(id_)
        return loc.item if loc else None

    def parent(self, item: dict) -> dict | None:
        loc = self.locs().get(item.get("id"))
        return self.item(loc.parent) if loc and loc.parent else None


def walk(item: dict, lists: dict):
    """Items in tree order (pre-order), the given one first."""
    yield item
    for key in child_keys(item, lists):
        for child in item.get(key, []):
            yield from walk(child, lists)


def subtree_ids(item: dict, lists: dict) -> list[str]:
    return [i["id"] for i in walk(item, lists)]


def fields(item: dict, lists: dict) -> dict:
    """An item's own values: everything except its id and its child lists."""
    keys = child_keys(item, lists)
    if not keys:                                    # most items (a note, a hit) hold no child lists
        return {k: v for k, v in item.items() if k != "id"}
    skip = set(keys) | {"id"}
    return {k: v for k, v in item.items() if k not in skip}


def bare(item: dict, lists: dict) -> dict:
    """The item with its child lists emptied (diff inserts children one by one)."""
    out = dict(item)
    for key in child_keys(item, lists):
        out[key] = []
    return out
