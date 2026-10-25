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
from .fields import KEY_FIELDS
from .marked import id_part, marked, order, same_time

TIME = dict(min=0, max=36000, unit="s")                         # a moment to read or set a value at
KEY_TIME = dict(min=-36000, max=36000, unit="s", markers=True)  # where a key sits: seconds or "#drop+0.2" (marked.py)
V = Param.number("v", label="Value", help="For a number field")
BY = Param.number("by", label="By", help="Instead of a value: how much to add to each target's own value now (+20; a doubling is by = its value)")
C = Param.color("c", label="Colour", help="For a colour field")
EASE = Param.choice("ease", EASES, label="Ease", help="Shapes the way to the next key")
FROM = Param.text("from", label="From", importance="deep",
                  help="Optional words on where the key came from (lip sync: the sound it was made from)")
# the curve of a key, as fields: a custom ease's handles, a spring's bounce and speed (each valid only for its ease)
SHAPE_EASE = {"x1": "custom", "y1": "custom", "x2": "custom", "y2": "custom", "bounce": "spring", "speed": "spring"}
SHAPE = [p for p in KEY_FIELDS if p.name in SHAPE_EASE]


def checked_shape(ctx, args: dict, ease, where: str) -> dict:
    """The curve fields in `args` ({"bounce": 0.3}), range-checked and only for the ease they belong to (`ease`: the
    key's ease after this change). Refused loudly otherwise."""
    out = {}
    for p in SHAPE:
        if p.name not in args:
            continue
        if ease != SHAPE_EASE[p.name]:
            ctx.fail(codes.BAD_ARGUMENT, f'"{p.name}"', f"only applies to a {SHAPE_EASE[p.name]} ease, and this key's ease is "
                     f"{ease or 'smooth'}", hint=f'Give ease: "{SHAPE_EASE[p.name]}" too.')
        out[p.name] = p.check(args[p.name], where)
    return out


def key_id(owner: str, prop: str, t) -> str:
    """`title.opacity.k1500` (1.5 s), `title.opacity.k_drop_p200` ("#drop+0.2"); before 0: `k-200`."""
    return f"{owner}.{prop}.{id_part(t)}"


def register_key_ops(registry, *, owners, check_key: Callable, check_still: Callable,
                     settable: Callable | None = None, value_params: list[Param] | None = None,
                     key_add_help: str = "From then on its keys alone decide its value.",
                     prop_help: str = "The field to animate (x, opacity, fill …)",
                     field_sets: dict[str, list[str]] | None = None, value_now: Callable | None = None) -> Callable:
    """Register the four operations on `registry`; returns `put_key(ctx, owner_id, prop, t, args)` for ops that add
    keys too. `check_key(ctx, owner, prop, args)` -> (the key's value field 'v' | 'c' | 'd', the checked value);
    `check_still(ctx, owner, prop, args)` -> the checked value of a field with no keys (it also refuses a field
    that doesn't apply now); `settable(ctx, owner, prop)` refuses a field that can't change now. `key_add_help` and `prop_help` are the words
    each app uses in its operation descriptions. `field_sets` ({"pose": ["x", "y", …]}) lets key.add key a named set
    at once with each field's value now (`value_now(ctx, owner, prop, t)` -> {"v": 3.0}, or None for a field that
    owner can't key now: it is left out); key.add then takes `fields` instead of `prop` (K in the screens)."""
    vals = value_params if value_params is not None else [V, C]
    settable = settable or (lambda ctx, owner, prop: None)
    PROP = Param.text("prop", label="Field", required=not field_sets, help=prop_help)   # key.add: or `fields`
    PROP_NEEDED = Param.text("prop", label="Field", required=True, help=prop_help)       # value.set, key.clear: always
    sets = [Param.choice("fields", list(field_sets), label="Fields", help="Key this set of fields with their values now "
                         "(instead of prop and a value): " + "; ".join(f"{k}: {', '.join(v)}" for k, v in field_sets.items()))]         if field_sets else []

    def put_key(ctx, owner_id: str, prop: str, t: float, args: dict):
        """Add a key, or change the one already there (same field, same time)."""
        owner = ctx.item(owner_id)
        settable(ctx, owner, prop)
        field, value = check_key(ctx, owner, prop, args)
        existing = next((k for k in keys_of(owner, prop) if same_time(k["t"], t)), None)
        shape = checked_shape(ctx, args, args.get("ease", existing.get("ease", "smooth") if existing else "smooth"),
                              f"{ctx.where} › {owner_id}.{prop}")
        if existing:
            ctx.set(existing["id"], field, value)
            for k in ("ease", "from"):
                if k in args:
                    ctx.set(existing["id"], k, args[k])
            for k, v in shape.items():
                ctx.set(existing["id"], k, v)
            return
        taken = index(ctx.doc, ctx.kind.lists)
        id_ = key_id(owner_id, prop, t)
        if id_ in taken:                       # a moved key kept this id: count past it
            id_ = ids.counted(taken, id_)
        after = sum(1 for k in owner.get("keys", []) if (k["prop"], order(k["t"])) < (prop, order(t)))
        ctx.insert(owner_id, "keys", {"id": id_, "type": "key", "prop": prop, "t": t, field: value,
                                      "ease": args.get("ease", "smooth"), **shape,
                                      **({"from": args["from"]} if args.get("from") else {})}, after)

    @registry.operation("key.add", "Set a field's value at a time (adds a key, or changes the one at that time). "
                        + key_add_help, target=owners, label="Add key",
                        params=[PROP, *sets, Param.number("t", label="Time", required=True, **KEY_TIME), *vals, EASE, *SHAPE, FROM])
    def key_add(ctx, targets, args):
        if "fields" in args:
            return _key_set(ctx, targets, args)
        if "prop" not in args:
            ctx.fail(codes.BAD_ARGUMENT, '"prop"', "is required", hint='The field to key, or fields: "'
                     + '" | "'.join(field_sets or {}) + '" for a set.' if field_sets else "The field to key.")
        for t in targets:
            put_key(ctx, t, args["prop"], args["t"], args)

    def _key_set(ctx, targets, args):
        """K: every field of the set each target can key now, at its value now (one change)."""
        given = [p.name for p in (PROP, *vals) if p.name in args]
        if given:
            ctx.fail(codes.BAD_ARGUMENT, '"fields"', f"keys each field at its value now; leave out {', '.join(given)}")
        keyed = 0
        for t in targets:
            owner = ctx.item(t)
            for prop in field_sets[args["fields"]]:
                now = value_now(ctx, owner, prop, args["t"])
                if now is not None:
                    put_key(ctx, t, prop, args["t"], {**now, **({"ease": args["ease"]} if "ease" in args else {})})
                    keyed += 1
        if not keyed:
            ctx.fail(codes.BAD_ARGUMENT, f'fields "{args["fields"]}"', "has nothing these items can key now",
                     hint="Their fields may be driven by an expression or an auto layout, or every field already "
                     "holds this value.")

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
                        params=[PROP_NEEDED, Param.number("at", label="At", help="The time (needed when the field is animated)",
                                                   **TIME), BY, *vals])
    def value_set(ctx, targets, args):
        if "by" in args and any(k in args for k in ("v", "c", "d")):
            ctx.fail(codes.BAD_ARGUMENT, '"by"', "can't be given with a value (\"v\")", hint="Give the new value, or how much to add to each one's own value.")
        for t in targets:
            owner, prop, a = ctx.item(t), args["prop"], args
            settable(ctx, owner, prop)
            if "by" in args:         # added to this item's own value now (at `at` for an animated field)
                keys = keys_of(owner, prop)
                if keys and "at" not in args:
                    ctx.fail(codes.BAD_ARGUMENT, '"at"', f"is needed: {t}.{prop} is animated", hint="Give the time.")
                now = track_value(keys, args["at"]) if keys else owner.get(prop)
                if isinstance(now, bool) or not isinstance(now, (int, float)):
                    ctx.fail(codes.BAD_ARGUMENT, '"by"', f"only changes a number; {t}.{prop} is not one")
                a = {**{k: v for k, v in args.items() if k != "by"}, "v": now + args["by"]}
            if keys_of(owner, prop):
                if "at" not in a:
                    ctx.fail(codes.BAD_ARGUMENT, '"at"', f"is needed: {t}.{prop} is animated", hint="Give the time.")
                put_key(ctx, t, prop, a["at"], a)
            else:
                ctx.set(t, prop, check_still(ctx, owner, prop, a))

    @registry.operation("key.clear", "Stop animating a field: delete its keys and keep its value at `at` as the still value.",
                        target=owners, label="Stop animating", importance="secondary",
                        params=[PROP_NEEDED, Param.number("at", label="At", default=0.0, **TIME)])
    def key_clear(ctx, targets, args):
        for t in targets:
            keys = keys_of(ctx.item(t), args["prop"])
            if not keys:
                ctx.fail(codes.BAD_ARGUMENT, f'prop "{args["prop"]}"', f"is not animated on {t}")
            if any(marked(k) for k in keys):        # its value at `at` needs the project's markers
                ctx.fail(codes.BAD_ARGUMENT, f'prop "{args["prop"]}"', f"has keys timed on a marker on {t}; the "
                         "value they leave depends on where the markers are", hint="Set the still value you want "
                         "after: key.clear with no marker keys, or key.remove each key, then value.set.")
            ctx.set(t, args["prop"], track_value(keys, args.get("at", 0.0)))
            for k in keys:
                ctx.remove(k["id"])

    return put_key
