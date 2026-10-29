"""Keys: the one way anything moves. The four generic operations (key.add, key.remove, value.set, key.clear) come
from rostrum_core.keys; this file gives them 2D's field rules (`d` shapes and width profiles, expressions, valid-when) and adds the
curve of a field (key.handles). A key's id comes from its owner, field and time (`title.opacity.k1500`).
Changing a key's time, value or ease is `key.set` (generated in kind.py).
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys import key_value, keys_of, register_key_ops
from rostrum_core.keys.curve import curve_of, handles_of  # noqa: F401  (the one curve reading, shared with 3D: mcp/curves.py, the curve view)

from . import fields as F, pathdata
from .kind import REGISTRY as R, check_text

OWNERS = F.ANIMATED_OWNERS
D = Param.text("d", label="Shape", help="For a path's shape: SVG path data (kept as absolute M, L, C, Z), morphed between keys; "
               "for its widthProfile: \"pos,mult …\", blended between keys")
V = Param.number("v", label="Value", help="For a number field")
C = Param.color("c", label="Colour", help="For a colour field")

_KINDS = {"v": "number", "c": "colour", "d": "text (path data or width profile)"}


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
            if prop == "d":
                value = pathdata.normalize(value)            # any SVG path data, stored as M L C Z
            check_text(prop, value)
        except ValueError as e:
            ctx.fail(codes.BAD_ARGUMENT, '"d"', str(e), hint='"pos,mult pos,mult …", positions 0..1 increasing, multipliers 0 or more.'
                     if prop == "widthProfile" else "SVG path data: M L H V C S Q T A Z (lower case relative).")
    return want, value


def settable(ctx, owner: dict, prop: str):
    """A field a value or key can change now: not driven by an expression (exprbake.py), and valid right now (its
    `valid_when`; e.g. a text following a path layer takes x, y, turn and scale from the path). Else refused, loudly."""
    from rostrum_core.conditions import holds
    from .exprbake import source_of
    if prop in F.FIXED.get(owner["type"], ()):
        ctx.fail(codes.BAD_ARGUMENT, f'{owner["id"]}.{prop}', "is written by the scene itself and never changed",
                 hint="Home is where the frame's centre was when the scene was made; move the frame with x and y.")
    if source := source_of(owner, prop):
        ctx.fail(codes.CONFLICT, f'{owner["id"]}.{prop}', f"is driven by an expression ({source}); a value or key would do nothing",
                 hint="expr.clear it first.")
    p = F.param(owner["type"], prop)
    if p is not None and p.valid_when is not None and not holds(p.valid_when, _Values(owner),
                                                                _facts(ctx, owner, p.valid_when)):
        from rostrum_core.conditions import describe
        when = describe(p.valid_when, {q.name: q.label for q in F.FIELDS[owner["type"]]})
        ctx.fail(codes.BAD_ARGUMENT, f'{owner["id"]}.{prop}', "doesn't apply right now",
                 hint=f"{p.label or prop} only works when {when}; it is not on the screen until then.")


class _Values:
    """The owner's values as a condition reads them (`get` only): its own, else its field's default."""

    def __init__(self, owner: dict):
        self.owner = owner

    def get(self, name, default=None):
        if name in self.owner:
            return self.owner[name]
        p = F.param(self.owner["type"], name)
        return p.default if p is not None else default


_NAMES: dict = {}       # id(condition) -> (condition, the facts it reads)


def _facts(ctx, owner: dict, cond) -> dict:
    """Only the facts the condition reads (a drag of 200 layers checks x and y of each, every step)."""
    from rostrum_core.conditions import refs
    from rostrum_core.tree import View
    from .kind import facts
    got = _NAMES.get(id(cond))
    if got is None or got[0] is not cond:
        got = _NAMES[id(cond)] = (cond, frozenset(n for k, n in refs(cond) if k == "fact"))
    return facts(owner, View(ctx.doc, ctx.kind.lists, ctx.idx), only=got[1]) if got[1] else {}


def _still_value(ctx, owner: dict, prop: str, args: dict):
    p = F.param(owner["type"], prop)
    if p is None:
        ctx.fail(codes.BAD_ARGUMENT, f'prop "{prop}"', f"is not a field of a {owner['type']}",
                 [q.name for q in F.FIELDS[owner["type"]]])
    field = "c" if p.type == "color" else "v"
    if field not in args:
        ctx.fail(codes.BAD_ARGUMENT, f'"{field}"', "is required", hint=f"The new value of {prop}.")
    return p.check(args[field], f"{ctx.where} › {owner['id']}.{prop}")


POSE = ["x", "y", "scale", "zoom", "rotation", "opacity"]   # K: position, scale, rotation and opacity (UX_SPEC 3.17); the frame's zoom


def _value_now(ctx, owner: dict, prop: str, t):
    """{"v": value} of a pose field at own time t, or None where this owner can't key it now (no such field, driven
    by an expression or placed by an auto layout / a path) or where a key would change nothing. The one rule for what K
    keys (UX_SPEC 3.17): every field it can, except one whose keys already all hold this value — unless K keys another
    field of the same owner that does change: then K keys the whole pose, the still ones as holds, so a move added
    later starts here (production round: a frame's zoom crept from 0 s because K skipped it as "nothing")."""
    now = _keyable_value(ctx, owner, prop, t)
    if now is None or not adds_nothing(owner, prop, now):
        return None if now is None else {"v": now}
    for other in POSE:       # keys already at t left out: K's own keys from this same press (it keys field by field)
        if other != prop and (v := _keyable_value(ctx, owner, other, t)) is not None and not _flat_besides(owner, other, v, t):
            return {"v": now}
    return None


def _flat_besides(owner: dict, prop: str, v, t) -> bool:
    keys = [k for k in keys_of(owner, prop) if k["t"] != t]
    return bool(keys) and all(key_value(k) == v for k in keys)


def _keyable_value(ctx, owner: dict, prop: str, t):
    """The value K would key for this field at own time t, or None where this owner can't key it now."""
    from rostrum_core.conditions import holds
    from .evaluate import value_at
    from .exprbake import source_of
    if prop not in F.animatable(owner["type"]) or source_of(owner, prop) or isinstance(t, str):
        return None
    p = F.param(owner["type"], prop)
    if not holds(p.valid_when, {**F.defaults(owner["type"]), **owner}, ctx.facts(owner)):
        return None
    keys = keys_of(owner, prop)
    if any(isinstance(k["t"], str) for k in keys):     # timed on a marker: the value needs the markers; left out
        return None
    return value_at(owner, prop, t)


def adds_nothing(owner: dict, prop: str, v) -> bool:
    """A key of `v` would change nothing: the field is animated and every key already holds `v`. The one test K, K on
    a rig (rig.key) and Apply pose (pose.apply) share, so none of them makes a flat field."""
    keys = keys_of(owner, prop)
    return bool(keys) and all(key_value(k) == v for k in keys)


class _Seen:
    """What `_value_now` reads of an operation's context, for the screens asking before they call (K)."""
    def __init__(self, doc):
        self.doc = doc

    def facts(self, item: dict) -> dict:
        return self.doc.kind.facts(item, self.doc)


def keyable_now(doc, owner: dict, t) -> bool:
    """K would key something on this owner at own time t (the same rule key.add fields "pose" follows)."""
    return any(_value_now(_Seen(doc), owner, p, t) is not None for p in POSE)


put_key = register_key_ops(R, owners=OWNERS, check_key=_checked_value, check_still=_still_value, settable=settable,
                           value_params=[V, C, D], key_add_help="The field is animated from then on: its keys alone decide its value.",
                           field_sets={"pose": POSE}, value_now=_value_now)


# ---- the curve of a field: the keys as an agent or the curve editor draws them ---------------------------------
@R.operation("key.handles", "Shape the stretch from a key to the next one with a cubic Bézier (x1 y1 x2 y2, as in CSS "
             "cubic-bezier): the key's ease becomes `custom`. y may leave 0..1 for overshoot. Start from a named "
             "ease's numbers (look_motion (what: curve) shows them).", target="key", label="Curve handles",
             params=[Param.number("x1", label="Curve x1", min=0, max=1, required=True),
                     Param.number("y1", label="Curve y1", min=-2, max=3, required=True),
                     Param.number("x2", label="Curve x2", min=0, max=1, required=True),
                     Param.number("y2", label="Curve y2", min=-2, max=3, required=True)])
def key_handles(ctx, targets, args):
    for t in targets:
        ctx.set(t, "ease", "custom")
        for n in ("x1", "y1", "x2", "y2"):
            ctx.set(t, n, args[n])
