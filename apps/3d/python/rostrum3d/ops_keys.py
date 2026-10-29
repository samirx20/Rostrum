"""Keys: the one way anything moves, the same key shape as 2D (`t` seconds, `v` or `c`, `ease`) with the same
operations: key.add, key.remove, value.set and key.clear come from rostrum_core.keys; this file gives them 3D's
field rules. A key's id comes from its owner, field and time (`key_light.x.k1500`). Changing a key's time,
value or ease is `key.set` (kind.py).
"""
from __future__ import annotations

from rostrum_core.errors import codes
from rostrum_core.keys import register_key_ops, register_layer_ops

from . import fields as F
from .kind import REGISTRY as R


def _field(ctx, owner: dict, prop: str, args: dict, animating: bool):
    """(the key/value field name 'v' or 'c', the checked value) under the owner's own rules for `prop`."""
    allowed = F.animatable(owner["type"]) if animating else [p.name for p in F.FIELDS[owner["type"]]]
    p = F.param(owner["type"], prop)
    if prop in allowed and F.is_toggle(owner["type"], prop):
        return "v", _toggle(ctx, owner, prop, args, animating)
    if prop not in allowed or p.type not in ("number", "color"):
        ctx.fail(codes.BAD_ARGUMENT, f'prop "{prop}"', f"is not an {'animatable ' if animating else ''}number or "
                 f"colour field of a {owner['type']}", F.animatable(owner["type"]))
    want, other = ("c", "v") if p.type == "color" else ("v", "c")
    if other in args or want not in args:
        ctx.fail(codes.BAD_ARGUMENT, f'"{want}"', f"is required: {prop} is a {'colour' if want == 'c' else 'number'}",
                 hint=f"Give {want}.")
    return want, p.check(args[want], f"{ctx.where} › {owner['id']}.{prop}")


def _toggle(ctx, owner: dict, prop: str, args: dict, animating: bool):
    """A keyable toggle (Visible): v is 1 (on) or 0 (off), or true / false. A key holds 1.0 / 0.0 (a key's value is a
    number); a still value is True / False."""
    v = args.get("v")
    if "c" in args or v not in (0, 1):                   # True == 1, False == 0
        ctx.fail(codes.BAD_ARGUMENT, '"v"', f"is required: {prop} is on / off, so v is 1 (on) or 0 (off)", hint="Give v: 1 or 0.")
    return (1.0 if v else 0.0) if animating else bool(v)


def _check_key(ctx, owner: dict, prop: str, args: dict):
    return _field(ctx, owner, prop, args, True)


def _check_still(ctx, owner: dict, prop: str, args: dict):
    value = _field(ctx, owner, prop, args, False)[1]
    if F.not_valid(owner["type"], owner, [prop]):
        ctx.fail(codes.BAD_ARGUMENT, f'prop "{prop}"', f"doesn't apply to {owner['id']} as it is now (rule of "
                 f"individuality)", hint=f"Use {owner['type']}.set to change what it depends on too.")
    return value


put_key = register_key_ops(R, owners=F.KEYED, check_key=_check_key, check_still=_check_still,
                           prop_help="The field to animate (x, ry, intensity, color …; visible: v 1 shows, 0 hides, held until the next key)",
                           layers=True)
register_layer_ops(R)            # animlayer.add / set / remove / move (rostrum_core.keys.layers)
