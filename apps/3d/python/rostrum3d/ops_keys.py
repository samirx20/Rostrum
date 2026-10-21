"""Keys: the one way anything moves, the same key shape as 2D (`t` seconds, `v` or `c`, `ease`) and the same
evaluator and easing table (rostrum2d.evaluate / rostrum2d.easing, until they move to rostrum_core). A key's id
comes from its owner, field and time (`key_light.x.k1500`), so a script re-run that writes the same key finds
it, and a person's change to it is kept. Changing a key's time, value or ease is `key.set` (kind.py).
"""
from __future__ import annotations

from rostrum_core import Param, ids
from rostrum_core.errors import codes
from rostrum_core.tree import index
from rostrum2d.easing import NAMES as EASES
from rostrum2d.evaluate import keys_of, track_value

from . import fields as F
from .kind import REGISTRY as R

PROP = Param.text("prop", label="Field", required=True, help="The field to animate (x, ry, intensity, color …)")
V = Param.number("v", label="Value", help="For a number field")
C = Param.color("c", label="Colour", help="For a colour field")
EASE = Param.choice("ease", EASES, label="Ease", help="Shapes the way to the next key")
TIME = dict(min=0, max=36000, unit="s")


def key_id(owner: str, prop: str, t: float) -> str:
    return ids.from_content(f"{owner}.{prop}", "k", t * 1000)


def _field(ctx, owner: dict, prop: str, args: dict, animating: bool):
    """(the key/value field name 'v' or 'c', the checked value) under the owner's own rules for `prop`."""
    allowed = F.animatable(owner["type"]) if animating else [p.name for p in F.FIELDS[owner["type"]]]
    p = F.param(owner["type"], prop)
    if prop not in allowed or p.type not in ("number", "color"):
        ctx.fail(codes.BAD_ARGUMENT, f'prop "{prop}"', f"is not an {'animatable ' if animating else ''}number or "
                 f"colour field of a {owner['type']}", F.animatable(owner["type"]))
    want, other = ("c", "v") if p.type == "color" else ("v", "c")
    if other in args or want not in args:
        ctx.fail(codes.BAD_ARGUMENT, f'"{want}"', f"is required: {prop} is a {'colour' if want == 'c' else 'number'}",
                 hint=f"Give {want}.")
    return want, p.check(args[want], f"{ctx.where} › {owner['id']}.{prop}")


def put_key(ctx, owner_id: str, prop: str, t: float, args: dict):
    """Add a key, or change the one already there (same field, same time)."""
    owner = ctx.item(owner_id)
    field, value = _field(ctx, owner, prop, args, True)
    existing = next((k for k in keys_of(owner, prop) if abs(k["t"] - t) < 1e-6), None)
    if existing:
        ctx.set(existing["id"], field, value)
        if "ease" in args:
            ctx.set(existing["id"], "ease", args["ease"])
        return
    taken = index(ctx.doc, ctx.kind.lists)
    id_ = key_id(owner_id, prop, t)
    if id_ in taken:                       # a moved key kept this id: count past it
        id_ = ids.counted(taken, id_)
    after = sum(1 for k in owner.get("keys", []) if (k["prop"], k["t"]) < (prop, t))
    ctx.insert(owner_id, "keys", {"id": id_, "type": "key", "prop": prop, "t": t, field: value,
                                  "ease": args.get("ease", "smooth")}, after)


@R.operation("key.add", "Set a field's value at a time (adds a key, or changes the one at that time). From then on "
             "its keys alone decide its value.", target=F.ITEMS, label="Add key",
             params=[PROP, Param.number("t", label="Time", required=True, **TIME), V, C, EASE])
def key_add(ctx, targets, args):
    for t in targets:
        put_key(ctx, t, args["prop"], args["t"], args)


@R.operation("key.remove", "Delete keys. A field whose last key goes keeps that key's value as its still value.",
             target="key", label="Delete key", importance="secondary")
def key_remove(ctx, targets, args):
    for t in targets:
        loc = index(ctx.doc, ctx.kind.lists)[t]
        owner, key = ctx.item(loc.parent), loc.item
        if len(keys_of(owner, key["prop"])) == 1:
            ctx.set(owner["id"], key["prop"], key.get("c", key.get("v")))
        ctx.remove(t)


@R.operation("value.set", "Change a field as a person sees it now: a still field changes; an animated field gets a "
             "key at `at`.", target=F.ITEMS, label="Set value",
             params=[PROP, Param.number("at", label="At", help="The time (needed when the field is animated)", **TIME),
                     V, C])
def value_set(ctx, targets, args):
    for t in targets:
        owner, prop = ctx.item(t), args["prop"]
        if keys_of(owner, prop):
            if "at" not in args:
                ctx.fail(codes.BAD_ARGUMENT, '"at"', f"is needed: {t}.{prop} is animated", hint="Give the time.")
            put_key(ctx, t, prop, args["at"], args)
        else:
            value = _field(ctx, owner, prop, args, False)[1]
            if F.not_valid(owner["type"], owner, [prop]):
                ctx.fail(codes.BAD_ARGUMENT, f'prop "{prop}"', f"doesn't apply to {t} as it is now (rule of "
                         f"individuality)", hint=f"Use {owner['type']}.set to change what it depends on too.")
            ctx.set(t, prop, value)


@R.operation("key.clear", "Stop animating a field: delete its keys and keep its value at `at` as the still value.",
             target=F.ITEMS, label="Stop animating", importance="secondary",
             params=[PROP, Param.number("at", label="At", default=0.0, **TIME)])
def key_clear(ctx, targets, args):
    for t in targets:
        keys = keys_of(ctx.item(t), args["prop"])
        if not keys:
            ctx.fail(codes.BAD_ARGUMENT, f'prop "{args["prop"]}"', f"is not animated on {t}")
        ctx.set(t, args["prop"], track_value(keys, args.get("at", 0.0)))
        for k in keys:
            ctx.remove(k["id"])
