"""A top-level layer's placement carried through a similarity of the plane: layer.pin (into or out of the frame's own
px), layer.set_depth (to where it shows at its new depth) and a resize's pinned layers (a shift). A similarity
m = (a, b, c, d, e, f) (view.py's matrices) takes the anchor point (x, y) to m · (x, y), multiplies `scale` by its size
k = |(a, b)| and adds its turn atan2(b, a) to `rotation`, on the still values AND every key, spatial handles
included, so an animated layer keeps the shape of its motion. Stretch (scaleX, scaleY) and the anchor stay: a uniform
scale changes only `scale`.

Under a turn x and y mix, so their keys are carried in pairs: x and y keyed at the same times with the same ease (a
still one gets keys at the other's times, the same ease), else refused loudly. Without a turn each field goes alone."""
from __future__ import annotations

import math

from rostrum_core.errors import codes
from rostrum_core.keys import keys_of
from rostrum_core.keys.marked import order, same_time
from rostrum_core.tree import index

from .. import fields as F

FIELDS = ("x", "y", "scale", "rotation")
_OWN = {"id", "type", "prop", "t", "v", "out", "in"}       # the rest of a key (ease, its curve …) is its timing


def inverse(m) -> tuple:
    a, b, c, d, e, f = m
    det = a * d - b * c
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return (ia, ib, ic, id_, -(ia * e + ic * f), -(ib * e + id_ * f))


def then(first, second) -> tuple:
    """`first`, then `second`: p ↦ second · (first · p)."""
    a, b, c, d, e, f = second
    a1, b1, c1, d1, e1, f1 = first
    return (a * a1 + c * b1, b * a1 + d * b1, a * c1 + c * d1, b * c1 + d * d1, a * e1 + c * f1 + e, b * e1 + d * f1 + f)


def check(ctx, layer: dict):
    """Refuses, naming the layer and field, a layer whose place can't be carried: riding a path (its place comes from
    the path) or a field a value can't change now (an expression drives it, a text follows a path …)."""
    from ..ops_keys import settable
    if layer.get("ridePath"):
        ctx.fail(codes.CONFLICT, f'{layer["id"]}.ridePath', f'rides "{layer["ridePath"]}": its place comes from the path',
                 hint='Use keep "values", or layer.ride it off the path first.')
    for f in FIELDS:
        settable(ctx, layer, f)


def carry(ctx, lid: str, m) -> None:
    """Carry layer `lid`'s x, y, scale and rotation through the similarity `m` (one change, part of the caller's)."""
    layer = ctx.item(lid)
    check(ctx, layer)
    a, b, c, d, e, f = m
    k, turn = math.hypot(a, b), math.degrees(math.atan2(b, a))
    if abs(b) < 1e-12 and abs(c) < 1e-12:
        _track(ctx, layer, "x", lambda v: a * v + e, a)
        _track(ctx, layer, "y", lambda v: d * v + f, d)
    else:
        _pairs(ctx, layer, m)
    _track(ctx, layer, "scale", lambda v: v * k, k)
    _track(ctx, layer, "rotation", lambda v: v + turn, 1.0)


def _put(ctx, owner: dict, id_: str, field: str, prop: str, old, v):
    if abs(v - old) > 1e-9:
        ctx.set(id_, field, F.param(owner["type"], prop).check(round(v, 6), f'{ctx.where} › {owner["id"]}.{prop}'))


def _track(ctx, layer, prop, fn, lin):
    """One field alone: values through fn, handles (offsets) times lin."""
    keys = keys_of(layer, prop)
    if not keys:
        old = float(layer.get(prop, F.param(layer["type"], prop).default))
        return _put(ctx, layer, layer["id"], prop, prop, old, fn(old))
    for key in keys:
        _put(ctx, layer, key["id"], "v", prop, key["v"], fn(key["v"]))
        for h in ("out", "in"):
            if h in key and abs(lin - 1) > 1e-12:
                ctx.set(key["id"], h, round(key[h] * lin, 6))


def _pairs(ctx, layer, m):
    a, b, c, d, e, f = m
    xs, ys = (_keyed(ctx, layer, p, o) for p, o in (("x", "y"), ("y", "x")))
    if not xs:                                             # both still
        x, y = (float(layer.get(p, F.param(layer["type"], p).default)) for p in ("x", "y"))
        _put(ctx, layer, layer["id"], "x", "x", x, a * x + c * y + e)
        _put(ctx, layer, layer["id"], "y", "y", y, b * x + d * y + f)
        return
    if len(xs) != len(ys) or any(not same_time(kx["t"], ky["t"]) or _timing(kx) != _timing(ky) for kx, ky in zip(xs, ys)):
        ctx.fail(codes.CONFLICT, f'{layer["id"]}.x, y', "are keyed at different times or with different eases, so turning "
                 "them with the frame would bend their path", hint='Key x and y together (K), or use keep "values".')
    vx, vy = [k["v"] for k in xs], [k["v"] for k in ys]
    hx, hy = _handles(xs, vx), _handles(ys, vy)
    for i, (kx, ky) in enumerate(zip(xs, ys)):
        _put(ctx, layer, kx["id"], "v", "x", vx[i], a * vx[i] + c * vy[i] + e)
        _put(ctx, layer, ky["id"], "v", "y", vy[i], b * vx[i] + d * vy[i] + f)
        for h in ("out", "in"):
            if h in kx or h in ky:
                ox, oy = hx[i][h], hy[i][h]
                ctx.set(kx["id"], h, round(a * ox + c * oy, 6))
                ctx.set(ky["id"], h, round(b * ox + d * oy, 6))


def _timing(key: dict) -> dict:
    return {k: v for k, v in key.items() if k not in _OWN}


def _handles(keys, vs) -> list[dict]:
    """Each key's out / in handle, a missing one as the straight line's third (spatial.py's default)."""
    n = len(keys)
    return [{"out": k.get("out", (vs[i + 1] - vs[i]) / 3 if i + 1 < n else 0.0),
             "in": k.get("in", -(vs[i] - vs[i - 1]) / 3 if i else 0.0)} for i, k in enumerate(keys)]


def _keyed(ctx, layer, prop, other) -> list[dict]:
    """`prop`'s keys; a still `prop` beside a keyed `other` first gets keys at other's times (its still value, other's
    timing), so the pair turns together. [] when neither is keyed."""
    keys = keys_of(layer, prop)
    if keys or not keys_of(layer, other):
        return keys
    v = float(layer.get(prop, F.param(layer["type"], prop).default))
    for ok in keys_of(layer, other):
        _insert(ctx, layer["id"], prop, ok["t"], {"v": v, **_timing(ok)})
    return keys_of(ctx.item(layer["id"]), prop)


def _insert(ctx, owner_id: str, prop: str, t, fields: dict):
    from rostrum_core import ids
    from rostrum_core.keys.ops import key_id
    owner, taken = ctx.item(owner_id), index(ctx.doc, ctx.kind.lists)
    id_ = key_id(owner_id, prop, t)
    id_ = ids.counted(taken, id_) if id_ in taken else id_
    after = sum(1 for k in owner.get("keys", []) if (k["prop"], order(k["t"])) < (prop, order(t)))
    ctx.insert(owner_id, "keys", {"id": id_, "type": "key", "prop": prop, "t": t, **fields}, after)
