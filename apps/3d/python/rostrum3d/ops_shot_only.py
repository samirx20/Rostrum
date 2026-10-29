"""Only in this shot (PR1, shot_layer.py): `<type>.set_in_shot` changes an item's (or a material's) settings for one shot
only, with the same settings `<type>.set` takes plus `shot`; `shot.clear_override` puts settings back to the all-shots
value in a shot. Each is one step (one undo). The values live in the shot's `overrides`, so a script re-run (which only
writes the fields its script gives) never wipes them.
"""
from __future__ import annotations

import dataclasses

from rostrum_core import Param
from rostrum_core.edits import MISSING
from rostrum_core.errors import codes

from . import fields as F, shot_layer as L
from .kind import REGISTRY as R

SHOT = Param.text("shot", label="Shot", required=True, help="The shot's id: the change shows in that shot only")


def _shot(ctx, shot_id: str) -> dict:
    shot = next((s for s in ctx.doc.get("shots", []) if s["id"] == shot_id), None)
    if shot is None:
        ctx.fail(codes.BAD_ARGUMENT, f'shot "{shot_id}"', "is not a shot",
                 [s["id"] for s in ctx.doc.get("shots", [])])
    return shot


def _set_in_shot(ctx, targets, args):
    shot = _shot(ctx, args["shot"])
    given = {k: v for k, v in args.items() if k != "shot"}
    if not given:
        ctx.fail(codes.BAD_ARGUMENT, "settings", "none given", hint='Give the settings to change, e.g. intensity=3.')
    for t in targets:
        item = ctx.item(t)
        if item.get("mirror"):
            ctx.fail(codes.BAD_ARGUMENT, f'"{t}"', "is a mirrored copy", hint=f'Change its original "{item["mirror"]}" in this shot.')
        if bad := F.not_valid(item["type"], item, given):
            ctx.fail(codes.BAD_ARGUMENT, f'"{t}"', f"has no {', '.join(bad)} as it is now")
        own = L.of(ctx.item(shot["id"]))
        keyed = {k["prop"] for k in item.get("keys", [])}
        mine = {**own.get(t, {}), **given}
        for k in given:                                 # the all-shots value again (unkeyed): the shot follows the rest
            if k not in keyed and k in item and item[k] == given[k]:
                mine.pop(k)
        every = {**{i: v for i, v in own.items() if i != t}, **({t: mine} if mine else {})}
        ctx.set(shot["id"], L.FIELD, every or MISSING)  # whole: an undo puts it back exactly


for _type in L.TYPES:
    _params = [SHOT] + [dataclasses.replace(p, valid_when=None, required=False)
                        for p in F.FIELDS[_type] if L.overridable(_type, p.name)]
    R.operation(f"{_type}.set_in_shot", f"Change a {F.LABELS[_type].lower()}'s settings in one shot only (`shot`); "
                "the other shots keep the all-shots value. A keyed setting holds this one value through that shot; "
                "giving an unkeyed setting its all-shots value again drops the shot's own.",
                target=_type, params=_params, label="Only in this shot", importance="secondary")(_set_in_shot)


@R.operation("shot.clear_override", "Put an item's settings back to the all-shots value in this shot: the `fields` "
             "given, or every one the shot changed for that item when left out.", target="shot",
             label="Use all-shots value", importance="secondary", min_targets=1,
             params=[Param.text("item", label="Item", required=True, help="The item or material id"),
                     Param.list("fields", "text", label="Settings", help="Field names; all when left out")])
def clear_override(ctx, targets, args):
    item, names = args["item"], args.get("fields") or []
    for t in targets:
        every = L.of(ctx.item(t))
        left = {k: v for k, v in (every.get(item) or {}).items() if names and k not in names}
        if item not in every:
            continue
        rest = {**{i: v for i, v in every.items() if i != item}, **({item: left} if left else {})}
        ctx.set(t, L.FIELD, rest or MISSING)                # nothing left: the shot reads as an old one again
