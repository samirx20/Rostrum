"""Making one item: the one place a new item gets its defaults, child lists and checked values, so an item added
by an operation looks exactly like one a script made. Values follow the fields table (range, type) and the
rule of individuality (a field that doesn't apply to the item as made is never stored: a script is told in its reply,
"not used on a strip light", and everything else it wrote is applied; an operation call is refused, naming why).
"""
from __future__ import annotations

import re

from rostrum_core.errors import RostrumError, codes, did_you_mean

from . import fields as F

_AIMED = "An aimed item's turn is worked out from its aim; roll turns it around the way it points (roll=90 stands a strip on end)."
HINTS = {"rx": _AIMED, "ry": _AIMED, "rz": _AIMED,
         "roll": "Roll turns an aimed item: in a script give it with the aim, item.aim(target, roll=90)."}


def make(type_: str, id_: str, values: dict, where: str, unused: list | None = None) -> dict:
    own = F.param(type_, "name") is not None        # a clay step's name is one of its fields: "" (none) is a value
    name = values.get("name", "") if own else values.get("name") or id_
    item = {"id": id_, "type": type_, **F.defaults(type_, values), "name": str(name)}
    for key in F.LISTS.get(type_, []):
        item[key] = []
    fill(item, {k: v for k, v in values.items() if k != "name"}, where, unused)
    return item


def fill(item: dict, values: dict, where: str, unused: list | None = None) -> dict:
    """Write checked field values onto an item; unknown fields fail loudly. A field that doesn't apply to the item as it
    then is (seenByCamera on a strip light) is left as it was: with `unused` (a script's reply notes) it is said there
    and the rest is written, without it (an operation call) the call fails naming it."""
    type_ = item["type"]
    known = [p.name for p in F.FIELDS[type_]]
    if unused is not None and "aim" in values and "aim" in known:
        values = aim_form(item["id"], values, unused)
    before = {k: item[k] for k in values if k in item}
    for k, v in values.items():
        if k == "name":
            item["name"] = str(v)
            continue
        if k not in known:
            raise RostrumError(codes.BAD_ARGUMENT, where, f'"{k}"', f"is not a field of a {type_}", known,
                               did_you_mean(k, known))
        item[k] = F.param(type_, k).check(v, f'{where} › {item["id"]}.{k}')
    bad = F.not_valid(type_, item, values)
    if bad and unused is None:
        p = F.param(type_, bad[0])
        from rostrum_core.conditions import describe
        raise RostrumError(codes.BAD_ARGUMENT, where, f'{item["id"]}.{bad[0]}',
                           f"only applies when {describe(p.valid_when)}", hint=HINTS.get(bad[0], f"Set that too to use {bad[0]}."))
    for k in bad:
        item.pop(k, None) if k not in before else item.__setitem__(k, before[k])
        unused.append(not_used(item, k))
    return item


def aim_form(id_: str, values: dict, notes: list) -> dict:
    """A script's aim= given as what to aim at (aim="bottle", aim=bottle, aim=(0, 1, 0)), as agents write it on a light
    or camera, read as .aim(...) does: aim="item" with aimItem, or aim="point" with aimX/Y/Z; said in the reply."""
    v = values["aim"]
    if isinstance(v, str) and v in ("none", "point", "item"):
        return values
    out = dict(values)
    if isinstance(v, (tuple, list)) and len(v) == 3 and all(isinstance(c, (int, float)) for c in v):
        out.update(aim="point", aimX=float(v[0]), aimY=float(v[1]), aimZ=float(v[2]))
        notes.append(f"{id_}: aim={tuple(v)!r} was read as .aim({tuple(v)!r}): it points at that spot every frame")
        return out
    target = v if isinstance(v, str) else getattr(v, "id", None)
    if isinstance(target, str) and target:
        out.update(aim="item", aimItem=target)
        notes.append(f'{id_}: aim="{target}" was read as .aim({target}): it points at {target} every frame')
    return out


def not_used(item: dict, field: str) -> str:
    """`strip.seenByCamera = False: not used on a strip light (only when Kind is Dome); the rest was applied`."""
    from rostrum_core.conditions import describe
    type_ = item["type"]
    what = f'{item["kind"]} {type_}' if isinstance(item.get("kind"), str) and item.get("kind") else type_
    return (f'{item["id"]}.{field}: not used on a{"n" if what[0] in "aeiou" else ""} {what} (it only applies when '
            f'{describe(F.param(type_, field).valid_when)}); everything else was applied')


def part_id(import_id: str, path: str) -> str:
    """A part's id from its import and path (`phone.Body_Screen`): the same path gives the same id every run."""
    return f"{import_id}." + (re.sub(r"[^A-Za-z0-9_]+", "_", path.strip("/")) or "root")
