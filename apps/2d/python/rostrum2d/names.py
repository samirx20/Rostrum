"""What an item is called. The id is the item's address and never changes; the name is what a person reads.

A new layer is named in words ("Text", then "Text 2", "Text 3" …). An older document may hold a layer whose name is only
its type's ("Text") with a meaningful id ("title"): there the id reads better, so it is shown instead."""
from __future__ import annotations

import re

from . import fields as F


def display_name(item: dict) -> str:
    """The name to show: the item's name; its id while the name says nothing the id doesn't ("Text" on "title")."""
    name, id_ = item.get("name"), str(item["id"])
    if not name:
        return id_
    if name == F.LABELS.get(item.get("type")) and not re.fullmatch(rf"{re.escape(item['type'])}_\d+", id_):
        return id_
    return str(name)


def unique_name(taken: set[str], base: str) -> str:
    """`base`, or `base 2`, `base 3` … the first that no item has."""
    if base not in taken:
        return base
    n = 2
    while f"{base} {n}" in taken:
        n += 1
    return f"{base} {n}"
