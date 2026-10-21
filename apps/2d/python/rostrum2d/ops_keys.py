"""Keys: the one way anything moves. A key's id comes from its owner, field and time (`title.opacity.k1500`),
so a script re-run that writes the same key finds it, and a person's change to it is kept. A moved key keeps
its id. Changing a key's time, value or ease is `key.set` (generated in kind.py).
"""
from __future__ import annotations

from rostrum_core import Param, ids
from rostrum_core.errors import codes
from rostrum_core.tree import index

from . import fields as F, pathdata
from .easing import BEZIERS, NAMES as EASES
from .evaluate import key_value, keys_of, track_value
from .kind import REGISTRY as R

OWNERS = F.ANIMATED_OWNERS
PROP = Param.text("prop", label="Field", required=True, help="The field to animate (x, opacity, fill …)")
V = Param.number("v", label="Value", help="For a number field")
C = Param.color("c", label="Colour", help="For a colour field")
D = Param.text("d", label="Shape", help="For a path's shape: path data (absolute M, L, C, Z), morphed between keys")
EASE = Param.choice("ease", EASES, label="Ease", help="Shapes the way to the next key")

_KINDS = {"v": "number", "c": "colour", "d": "shape (path data)"}


def key_id(owner: str, prop: str, t: float) -> str:
    return ids.from_content(f"{owner}.{prop}", "k", t * 1000)


def _checked_value(ctx, owner: dict, prop: str, args: dict):
    """(field name on the key, value) after the owner's own field rules (range, colour)."""
    allowed = F.animatable(owner["type"])
    if prop not in allowed:
        ctx.fail(codes.BAD_ARGUMENT, f'prop "{prop}"', f"is not an animatable field of a {owner['type']}", allowed)
    p, want = F.param(owner["type"], prop), F.key_field(owner["type"], prop)
    for other in _KINDS:
        if other != want and other in args:
            ctx.fail(codes.BAD_ARGUMENT, f'"{other}"', f"{prop} is a {_KINDS[want]} field", hint=f"Give {want}.")
    if want not in args:
        ctx.fail(codes.BAD_ARGUMENT, f'"{want}"', "is required", hint=f"The value of {prop} at this time.")
    value = p.check(args[want], f"{ctx.where} › {owner['id']}.{prop}")
    if want == "d":
        try:
            pathdata.commands(value)
        except ValueError as e:
            ctx.fail(codes.BAD_ARGUMENT, '"d"', str(e), hint="Absolute M x y, L x y, C x1 y1 x2 y2 x y, Z.")
    return want, value


def settable(ctx, owner: dict, prop: str):
    """A field a value or key can change now: not driven by an expression (exprbake.py), and valid right now (its
    `valid_when`; e.g. a text following a path layer takes x, y, turn and scale from the path). Else refused, loudly."""
    from rostrum_core.conditions import holds
    from .exprbake import source_of
    if source := source_of(owner, prop):
        ctx.fail(codes.CONFLICT, f'{owner["id"]}.{prop}', f"is driven by an expression ({source}); a value or key would do nothing",
                 hint="expr.clear it first.")
    p = F.param(owner["type"], prop)
    if p is not None and not holds(p.valid_when, {**F.defaults(owner["type"]), **owner}):
        ctx.fail(codes.BAD_ARGUMENT, f'{owner["id"]}.{prop}', "doesn't apply right now", hint=f"It shows in the inspector only when it applies (fields.py valid_when {p.valid_when}).")


def put_key(ctx, owner_id: str, prop: str, t: float, args: dict):
    """Add a key, or change the one already there (same field, same time)."""
    owner = ctx.item(owner_id)
    settable(ctx, owner, prop)
    field, value = _checked_value(ctx, owner, prop, args)
    existing = next((k for k in keys_of(owner, prop) if abs(k["t"] - t) < 1e-6), None)
    if existing:
        ctx.set(existing["id"], field, value)
        if "ease" in args:
            ctx.set(existing["id"], "ease", args["ease"])
        return
    id_ = key_id(owner_id, prop, t)
    if id_ in index(ctx.doc, ctx.kind.lists):       # a moved key kept this id: count past it
        id_ = ids.counted(index(ctx.doc, ctx.kind.lists), id_)
    after = sum(1 for k in owner.get("keys", []) if (k["prop"], k["t"]) < (prop, t))
    ctx.insert(owner_id, "keys", {"id": id_, "type": "key", "prop": prop, "t": t, field: value,
                                  "ease": args.get("ease", "smooth")}, after)


@R.operation("key.add", "Set a field's value at a time (adds a key, or changes the one at that time). The field is "
             "animated from then on: its keys alone decide its value.", target=OWNERS, label="Add key",
             params=[PROP, Param.number("t", label="Time", min=0, max=36000, unit="s", required=True), V, C, D, EASE])
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
            ctx.set(owner["id"], key["prop"], key_value(key))
        ctx.remove(t)


@R.operation("value.set", "Change a field as a person sees it now: a still field changes; an animated field gets a "
             "key at `at`.", target=OWNERS, label="Set value",
             params=[PROP, Param.number("at", label="At", min=0, max=36000, unit="s",
                                        help="The time (needed when the field is animated)"), V, C, D])
def value_set(ctx, targets, args):
    for t in targets:
        owner, prop = ctx.item(t), args["prop"]
        settable(ctx, owner, prop)
        if keys_of(owner, prop):
            if "at" not in args:
                ctx.fail(codes.BAD_ARGUMENT, '"at"', f"is needed: {t}.{prop} is animated", hint="Give the time.")
            put_key(ctx, t, prop, args["at"], args)
            continue
        p = F.param(owner["type"], prop)
        if p is None:
            ctx.fail(codes.BAD_ARGUMENT, f'prop "{prop}"', f"is not a field of a {owner['type']}",
                     [q.name for q in F.FIELDS[owner["type"]]])
        field = "c" if p.type == "color" else "v"
        if field not in args:
            ctx.fail(codes.BAD_ARGUMENT, f'"{field}"', "is required", hint=f"The new value of {prop}.")
        ctx.set(t, prop, p.check(args[field], f"{ctx.where} › {t}.{prop}"))


@R.operation("key.clear", "Stop animating a field: delete its keys and keep its value at `at` as the still value.",
             target=OWNERS, label="Stop animating", importance="secondary",
             params=[PROP, Param.number("at", label="At", min=0, max=36000, unit="s", default=0.0)])
def key_clear(ctx, targets, args):
    for t in targets:
        keys = keys_of(ctx.item(t), args["prop"])
        if not keys:
            ctx.fail(codes.BAD_ARGUMENT, f'prop "{args["prop"]}"', f"is not animated on {t}")
        ctx.set(t, args["prop"], track_value(keys, args.get("at", 0.0)))
        for k in keys:
            ctx.remove(k["id"])


# ---- the curve of a field: the keys as an agent or the curve editor draws them ---------------------------------
def handles_of(key: dict) -> dict | None:
    """The four Bézier numbers {x1, y1, x2, y2} of the stretch from this key, or None where the ease has none
    (linear, hold, spring, bounce). A named cubic gives its own numbers: they are where a `custom` ease starts."""
    ease = key.get("ease", "smooth")
    if ease in BEZIERS:
        return dict(zip(("x1", "y1", "x2", "y2"), BEZIERS[ease]))
    if ease == "custom":
        return {n: key.get(n, d) for n, d in zip(("x1", "y1", "x2", "y2"), (0.25, 0.1, 0.25, 1.0))}
    return None


def curve_of(owner: dict, prop: str, per_stretch: int = 24) -> dict:
    """{"keys": [{id, t, v, ease, handles}], "samples": [[t, v] …]} of a number field, the samples from the one
    evaluation (track_value). Colour fields have no value curve: they raise ValueError."""
    keys = keys_of(owner, prop)
    if keys and "c" in keys[0]:
        raise ValueError(f"{owner['id']}.{prop} is a colour field: it has no value curve")
    samples: list[list[float]] = []
    for k0, k1 in zip(keys, keys[1:]):
        steps = 1 if k0.get("ease") == "hold" else per_stretch
        for i in range(steps):                       # a hold stays flat, then jumps at the next key
            t = k0["t"] + (k1["t"] - k0["t"]) * i / steps
            samples.append([t, track_value(keys, t)])
        if k0.get("ease") == "hold":
            samples.append([k1["t"], k0["v"]])
    if keys:
        samples.append([keys[-1]["t"], keys[-1]["v"]])
    return {"keys": [{"id": k["id"], "t": k["t"], "v": k["v"], "ease": k.get("ease", "smooth"),
                      "handles": handles_of(k) if i < len(keys) - 1 else None} for i, k in enumerate(keys)],
            "samples": samples}


@R.operation("key.handles", "Shape the stretch from a key to the next one with a cubic Bézier (x1 y1 x2 y2, as in CSS "
             "cubic-bezier): the key's ease becomes `custom`. y may leave 0..1 for overshoot. Start from a named "
             "ease's numbers (inspect_curve shows them).", target="key", label="Curve handles",
             params=[Param.number("x1", label="Curve x1", min=0, max=1, required=True),
                     Param.number("y1", label="Curve y1", min=-2, max=3, required=True),
                     Param.number("x2", label="Curve x2", min=0, max=1, required=True),
                     Param.number("y2", label="Curve y2", min=-2, max=3, required=True)])
def key_handles(ctx, targets, args):
    for t in targets:
        ctx.set(t, "ease", "custom")
        for n in ("x1", "y1", "x2", "y2"):
            ctx.set(t, n, args[n])
