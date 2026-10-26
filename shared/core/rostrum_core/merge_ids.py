"""A script's items keep their ids across runs when only their id moved (OPERATIONS.md § 7).

Apps make ids from content (Sound: a note's id is where it starts, in ms), so a change elsewhere can rename every item
a script makes without changing any of them: a new tempo moves each note written in beats to another millisecond.
Without this, a re-run removed and re-made them all, and a person's edit to one was held back on the old note while
the script's new copy played beside it (critic r9). Rule: an item the script makes now under a new id, equal in every
field but its id to one it made last time under an id it no longer makes, in the same place (parent and list), is
that item and keeps its id. Only items without child lists are matched (a child's id may be built from its parent's).
"""
from __future__ import annotations

import copy
import json

from .tree import child_keys, walk


def _places(data: dict, lists: dict):
    """(item, parent id, list key) for every item below the root, in tree order."""
    for item in walk(data, lists):
        for key in child_keys(item, lists):
            for child in item.get(key, []):
                yield child, item["id"], key


def _same(item: dict, parent: str, key: str) -> tuple:
    return parent, key, json.dumps({k: v for k, v in item.items() if k != "id"}, sort_keys=True, default=str)


def carried(base: dict, output: dict, lists: dict) -> dict:
    """`output` with renamed-only items given back their ids from `base` (a copy when any is; else `output` itself)."""
    made = {i["id"] for i, _, _ in _places(output, lists)}
    pool: dict[tuple, list[str]] = {}
    for item, parent, key in _places(base, lists):
        if item["id"] not in made and not child_keys(item, lists):
            pool.setdefault(_same(item, parent, key), []).append(item["id"])
    if not pool:
        return output
    was = {i["id"] for i, _, _ in _places(base, lists)}
    rename = {}
    for item, parent, key in _places(output, lists):
        if item["id"] not in was and not child_keys(item, lists):
            ids = pool.get(_same(item, parent, key))
            if ids:
                rename[item["id"]] = ids.pop(0)
    if not rename:
        return output
    output = copy.deepcopy(output)
    for item, _, _ in _places(output, lists):
        if item["id"] in rename:
            item["id"] = rename[item["id"]]
    return output
