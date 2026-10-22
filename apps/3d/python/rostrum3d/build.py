"""Making one item: the one place a new item gets its defaults, child lists and checked values, so an item added
by an operation looks exactly like one a script made. Values follow the fields table (range, type) and the
rule of individuality (a field that doesn't apply to the item as made is refused, never stored silently).
"""
from __future__ import annotations

import re

from rostrum_core.errors import RostrumError, codes, did_you_mean

from . import fields as F

_AIMED = "An aimed item's turn is worked out from its aim; roll turns it around the way it points (roll=90 stands a strip on end)."
HINTS = {"rx": _AIMED, "ry": _AIMED, "rz": _AIMED,
         "roll": "Roll turns an aimed item: in a script give it with the aim, item.aim(target, roll=90)."}


def make(type_: str, id_: str, values: dict, where: str) -> dict:
    item = {"id": id_, "type": type_, "name": str(values.get("name") or id_), **F.defaults(type_)}
    for key in F.LISTS.get(type_, []):
        item[key] = []
    fill(item, {k: v for k, v in values.items() if k != "name"}, where)
    return item


def fill(item: dict, values: dict, where: str) -> dict:
    """Write checked field values onto an item; unknown fields and fields that don't apply fail loudly."""
    type_ = item["type"]
    known = [p.name for p in F.FIELDS[type_]]
    for k, v in values.items():
        if k == "name":
            item["name"] = str(v)
            continue
        if k not in known:
            raise RostrumError(codes.BAD_ARGUMENT, where, f'"{k}"', f"is not a field of a {type_}", known,
                               did_you_mean(k, known))
        item[k] = F.param(type_, k).check(v, f'{where} › {item["id"]}.{k}')
    bad = F.not_valid(type_, item, values)
    if bad:
        p = F.param(type_, bad[0])
        from rostrum_core.conditions import describe
        raise RostrumError(codes.BAD_ARGUMENT, where, f'{item["id"]}.{bad[0]}',
                           f"only applies when {describe(p.valid_when)}", hint=HINTS.get(bad[0], f"Set that too to use {bad[0]}."))
    return item


def part_id(import_id: str, path: str) -> str:
    """A part's id from its import and path (`phone.Body_Screen`): the same path gives the same id every run."""
    return f"{import_id}." + (re.sub(r"[^A-Za-z0-9_]+", "_", path.strip("/")) or "root")
