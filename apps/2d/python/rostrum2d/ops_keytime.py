"""Retiming keys without re-keying (UX_SPEC 3.17): `key.scale` stretches or squeezes keys in time around a moment, and
`key.paste` puts copies of keys onto the same settings of other layers starting at a time, keeping their spacing.
Each is one operation, so one change and one undo step. Times are the owner's own seconds (as key.add's `t`); a key
on a shared marker stays on it (its offset changes).
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys import KEY_FIELDS, key_value, keys_of, marked
from rostrum_core.marker_times import seconds
from rostrum_core.tree import index

from . import fields as F
from .kind import REGISTRY as R
from .ops_keys import put_key
from .ops_timing import _times
from .retime import offset_of

SHAPING = [p.name for p in KEY_FIELDS if p.name not in ("t", "v", "c", "d", "ease")]   # x1 … bounce, speed


def _own_seconds(ctx, key: dict, owner_id: str) -> float:
    """A key's time in its owner's own seconds (a marker key placed through the project's markers)."""
    if not marked.marked(key):
        return float(key["t"])
    return seconds(key["t"], _times(ctx), key["id"]) - offset_of(ctx.doc, owner_id, _times(ctx))


def _owner(ctx, key_id: str) -> dict:
    loc = index(ctx.doc, ctx.kind.lists)[key_id]
    return ctx.item(loc.parent)


@R.operation("key.scale", "Stretch or squeeze keys in time around a moment: each key's time becomes around + (time - "
             "around) × by (by 2 = twice as slow, 0.5 = twice as fast). `around` is in the keys' owners' own seconds "
             "(the first key's time keeps the start where it is). Keys of one setting may not land on each other.",
             target="key", label="Stretch keys", importance="secondary",
             params=[Param.number("around", label="Around", min=-36000, max=36000, unit="s", required=True),
                     Param.number("by", label="By", min=0.01, max=100, step=0.01, unit="×", required=True)])
def key_scale(ctx, targets, args):
    around, by = float(args["around"]), float(args["by"])
    moved: dict[tuple[str, str], dict[str, tuple[float, float]]] = {}
    for kid in targets:
        owner = _owner(ctx, kid)
        key = ctx.item(kid)
        old = _own_seconds(ctx, key, owner["id"])
        moved.setdefault((owner["id"], key["prop"]), {})[kid] = (old, around + (old - around) * by)
    for (owner_id, prop), mine in moved.items():
        final = {k["id"]: mine[k["id"]][1] if k["id"] in mine else _own_seconds(ctx, k, owner_id)
                 for k in keys_of(ctx.item(owner_id), prop)}
        ts = sorted(final.values())
        if any(b - a < 1e-6 for a, b in zip(ts, ts[1:])):
            ctx.fail(codes.CONFLICT, f"{owner_id}.{prop}", f"would have two keys at the same time after stretching by {by:g}",
                     hint="Stretch less, or move the other key first.")
        for kid, (old, new) in mine.items():
            key = ctx.item(kid)
            ctx.set(kid, "t", marked.moved(key["t"], new - old) if marked.marked(key) else round(new, 6))


@R.operation("key.paste", "Paste copies of keys onto the same settings of the target layers (or effects, masks), the "
             "first copied key at `at` (the target's own seconds), the others keeping their spacing. Each key keeps its "
             "value and ease. A target without one of those settings is refused, naming it.",
             target=F.ANIMATED_OWNERS, label="Paste keys", importance="secondary",
             params=[Param.list("from", "id", label="Keys", required=True, help="The keys to copy (their ids)"),
                     Param.number("at", label="At", min=-36000, max=36000, unit="s", required=True)])
def key_paste(ctx, targets, args):
    src = []
    for kid in args["from"]:
        if kid not in index(ctx.doc, ctx.kind.lists) or ctx.item(kid).get("type") != "key":
            ctx.fail(codes.NOT_FOUND, f'from "{kid}"', "is not a key in this document", hint="Copy keys that still exist.")
        owner = _owner(ctx, kid)
        key = dict(ctx.item(kid))
        src.append((_own_seconds(ctx, key, owner["id"]) + offset_of(ctx.doc, owner["id"], _times(ctx)), key))
    first = min(t for t, _ in src)
    seen: set[tuple[str, str, float]] = set()
    for target in targets:
        owner = ctx.item(target)
        for t, key in sorted(src, key=lambda x: x[0]):
            at = round(float(args["at"]) + t - first, 6)
            if (target, key["prop"], at) in seen:
                ctx.fail(codes.CONFLICT, f'{target}.{key["prop"]}', f"would get two pasted keys at {at:g} s",
                         hint="Copy the keys of one layer at a time.")
            seen.add((target, key["prop"], at))
            field = next(f for f in ("v", "c", "d") if f in key)
            put_key(ctx, target, key["prop"], at, {field: key_value(key), "ease": key.get("ease", "smooth")})
            made = next(k for k in keys_of(ctx.item(owner["id"]), key["prop"]) if not marked.marked(k) and abs(k["t"] - at) < 1e-6)
            for name in SHAPING:
                if name in key:
                    ctx.set(made["id"], name, key[name])
