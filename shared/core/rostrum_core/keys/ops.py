"""The four generic key operations (`key.add`, `key.remove`, `value.set`, `key.clear`), registered on an app's
Registry by `register_key_ops`. A key's id comes from its owner, field and time (`title.opacity.k1500`), so a
script re-run that writes the same key finds it, and a person's change to it is kept. A moved key keeps its id.
Changing a key's time, value or ease is `key.set` (generated from the key fields table).

What differs per app is passed in: which items own keys, how a key's value is checked (`check_key`), how a still
value is checked (`check_still`), optionally `settable` (refuses a field a value or key can't change now, e.g. one
driven by an expression) and `value_params` (the value params a key takes; 2D adds `d`, a path's shape).
"""
from __future__ import annotations

from collections.abc import Callable

from .. import ids
from ..errors import codes
from ..params import Param
from ..tree import index
from .easing import NAMES as EASES
from .evaluate import key_value, keys_of, track_value

TIME = dict(min=0, max=36000, unit="s")
V = Param.number("v", label="Value", help="For a number field")
C = Param.color("c", label="Colour", help="For a colour field")
EASE = Param.choice("ease", EASES, label="Ease", help="Shapes the way to the next key")


def key_id(owner: str, prop: str, t: float) -> str:
    return ids.from_content(f"{owner}.{prop}", "k", t * 1000)


def register_key_ops(registry, *, owners, check_key: Callable, check_still: Callable,
                     settable: Callable | None = None, value_params: list[Param] | None = None,
                     key_add_help: str = "From then on its keys alone decide its value.",
                     prop_help: str = "The field to animate (x, opacity, fill …)") -> Callable:
    """Register the four operations on `registry`; returns `put_key(ctx, owner_id, prop, t, args)` for ops that add
    keys too. `check_key(ctx, owner, prop, args)` -> (the key's value field 'v' | 'c' | 'd', the checked value);
    `check_still(ctx, owner, prop, args)` -> the checked value of a field with no keys (it also refuses a field
    that doesn't apply now); `settable(ctx, owner, prop)` refuses a field that can't change now. `key_add_help` and `prop_help` are the words
    each app uses in its operation descriptions."""
    vals = value_params if value_params is not None else [V, C]
    settable = settable or (lambda ctx, owner, prop: None)
    PROP = Param.text("prop", label="Field", required=True, help=prop_help)

    def put_key(ctx, owner_id: str, prop: str, t: float, args: dict):
        """Add a key, or change the one already there (same field, same time)."""
        owner = ctx.item(owner_id)
        settable(ctx, owner, prop)
        field, value = check_key(ctx, owner, prop, args)
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

    @registry.operation("key.add", "Set a field's value at a time (adds a key, or changes the one at that time). "
                        + key_add_help, target=owners, label="Add key",
                        params=[PROP, Param.number("t", label="Time", required=True, **TIME), *vals, EASE])
    def key_add(ctx, targets, args):
        for t in targets:
            put_key(ctx, t, args["prop"], args["t"], args)

    @registry.operation("key.remove", "Delete keys. A field whose last key goes keeps that key's value as its still value.",
                        target="key", label="Delete key", importance="secondary")
    def key_remove(ctx, targets, args):
        for t in targets:
            loc = index(ctx.doc, ctx.kind.lists)[t]
            owner, key = ctx.item(loc.parent), loc.item
            if len(keys_of(owner, key["prop"])) == 1:
                ctx.set(owner["id"], key["prop"], key_value(key))
            ctx.remove(t)

    @registry.operation("value.set", "Change a field as a person sees it now: a still field changes; an animated field "
                        "gets a key at `at`.", target=owners, label="Set value",
                        params=[PROP, Param.number("at", label="At", help="The time (needed when the field is animated)",
                                                   **TIME), *vals])
    def value_set(ctx, targets, args):
        for t in targets:
            owner, prop = ctx.item(t), args["prop"]
            settable(ctx, owner, prop)
            if keys_of(owner, prop):
                if "at" not in args:
                    ctx.fail(codes.BAD_ARGUMENT, '"at"', f"is needed: {t}.{prop} is animated", hint="Give the time.")
                put_key(ctx, t, prop, args["at"], args)
            else:
                ctx.set(t, prop, check_still(ctx, owner, prop, args))

    @registry.operation("key.clear", "Stop animating a field: delete its keys and keep its value at `at` as the still value.",
                        target=owners, label="Stop animating", importance="secondary",
                        params=[PROP, Param.number("at", label="At", default=0.0, **TIME)])
    def key_clear(ctx, targets, args):
        for t in targets:
            keys = keys_of(ctx.item(t), args["prop"])
            if not keys:
                ctx.fail(codes.BAD_ARGUMENT, f'prop "{args["prop"]}"', f"is not animated on {t}")
            ctx.set(t, args["prop"], track_value(keys, args.get("at", 0.0)))
            for k in keys:
                ctx.remove(k["id"])

    return put_key
