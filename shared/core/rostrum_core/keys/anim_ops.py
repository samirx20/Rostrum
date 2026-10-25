"""Operations on whole animations and key timing, for any app's keyed items (`register_anim_ops`):
`anim.ease` (apps/2d SPEC §9.4) sets the ease of whole stretches in one change; `key.scale` stretches or squeezes keys
in time around a moment; `key.paste` puts copies of keys onto the same settings of other items at a time, keeping
their spacing; `key.stagger` (stagger.py) makes several items' keys start one after another. Each is one operation:
one change, one undo step. Times are the owner's own seconds (as key.add's `t`); a key on a shared marker stays on it.

What differs per app is passed in: its setting names (`names`, anims.Names), `put_key` (from register_key_ops), and
how an owner's own seconds sit in the scene (`timing`, a Timing: plain seconds by default).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..errors import codes
from ..params import Param
from ..tree import index
from . import marked
from .anims import PLAIN, Names
from .easing import EASE_LIST, OLD_NAMES
from .evaluate import key_value, keys_of
from .fields import KEY_FIELDS

CURVE = ("x1", "y1", "x2", "y2")
SHAPING = [p.name for p in KEY_FIELDS if p.name not in ("t", "v", "c", "d", "ease")]   # x1 … bounce, speed


@dataclass(frozen=True)
class Timing:
    """How keys sit in the scene's time. `own_seconds(ctx, key, owner_id)`: a key's time in its owner's seconds (a
    marker key placed through the project's markers); `offset(ctx, owner_id)`: where the owner's 0 is in the scene;
    `group_of(ctx, key_id)`: the item that moves as one in key.stagger (2D: the key's layer)."""
    own_seconds: Callable = lambda ctx, key, owner_id: float(key["t"])
    offset: Callable = lambda ctx, owner_id: 0.0
    group_of: Callable = lambda ctx, key_id: owner_of(ctx, key_id)["id"]


def owner_of(ctx, key_id: str) -> dict:
    return ctx.item(index(ctx.doc, ctx.kind.lists)[key_id].parent)


def register_anim_ops(registry, *, owners, put_key: Callable, names: Names = PLAIN, timing: Timing = Timing(),
                      orders=None) -> None:
    """Register anim.ease, key.scale, key.paste and key.stagger on `registry`. `owners`: the item types that own keys
    (key.paste's targets); `orders` (stagger.Orders) adds the app's own cascade orders to key.stagger."""
    from .stagger import register_key_stagger

    @registry.operation("anim.ease", "Ease whole stretches (the time between two keys of one setting) in one change: a "
                        "preset (an ease's id, the words key.set {ease} takes: " + ", ".join(e["id"] for e in EASE_LIST) +
                        '; "in" and "out" still mean easeIn and easeOut), or a curve (x1 y1 x2 y2, as CSS '
                        "cubic-bezier: the ease becomes custom), or a spring's bounce and speed. Targets: the keys each "
                        "stretch starts at (anim.list gives them as a stretch's ids). A setting's last key starts no "
                        "stretch and is refused.",
                        target="key", label="Ease", importance="secondary",
                        params=[Param.choice("preset", [*(e["id"] for e in EASE_LIST), *OLD_NAMES], label="Preset"),
                                Param.number("x1", label="Curve x1", min=0, max=1), Param.number("y1", label="Curve y1", min=-2, max=3),
                                Param.number("x2", label="Curve x2", min=0, max=1), Param.number("y2", label="Curve y2", min=-2, max=3),
                                Param.number("bounce", label="Bounce", min=0, max=1), Param.number("speed", label="Speed", min=0, max=1)])
    def anim_ease(ctx, targets, args):
        curve = [n for n in CURVE if n in args]
        spring = [n for n in ("bounce", "speed") if n in args]
        if curve and len(curve) < 4:
            ctx.fail(codes.BAD_ARGUMENT, '"x1 y1 x2 y2"', "a curve needs all four numbers", hint="Give x1, y1, x2 and y2.")
        if curve and "preset" in args:
            ctx.fail(codes.BAD_ARGUMENT, '"preset"', "give a preset or a curve, not both")
        if spring and args.get("preset", "spring") != "spring" or spring and curve:
            ctx.fail(codes.BAD_ARGUMENT, '"bounce" / "speed"', "only shape a spring", hint='Give preset: "spring" (or leave it out).')
        if not (curve or spring or "preset" in args):
            ctx.fail(codes.BAD_ARGUMENT, '"preset"', "is required (or a curve, or a spring's bounce / speed)")
        ease = "custom" if curve else "spring" if spring else OLD_NAMES.get(args["preset"], args["preset"])
        for kid in targets:
            _starts_stretch(ctx, kid)
            ctx.set(kid, "ease", ease)
            for n in (*curve, *spring):
                ctx.set(kid, n, args[n])

    def _starts_stretch(ctx, kid: str):
        """Refuse a key after which its setting has no other key (X and Y of Position count together)."""
        owner, key = owner_of(ctx, kid), ctx.item(kid)
        if marked.marked(key) or any(marked.marked(k) for k in owner.get("keys", [])):
            return                                        # a marker's time needs the markers: accepted as written
        setting = names.setting_of(key["prop"])
        later = [k for k in owner.get("keys", []) if names.setting_of(k["prop"]) == setting and k["t"] > key["t"] + 1e-6]
        if not later:
            ctx.fail(codes.BAD_ARGUMENT, f'key "{kid}"', f"is the last key of {owner['id']}.{setting}: no stretch starts there",
                     hint="Give the key a stretch starts at (anim.list › stretches › ids).")

    @registry.operation("key.scale", "Stretch or squeeze keys in time around a moment: each key's time becomes around + "
                        "(time - around) × by (by 2 = twice as slow, 0.5 = twice as fast). `around` is in the keys' owners' "
                        "own seconds (the first key's time keeps the start where it is). Keys of one setting may not land on each other.",
                        target="key", label="Stretch keys", importance="secondary",
                        params=[Param.number("around", label="Around", min=-36000, max=36000, unit="s", required=True),
                                Param.number("by", label="By", min=0.01, max=100, step=0.01, unit="×", required=True)])
    def key_scale(ctx, targets, args):
        around, by = float(args["around"]), float(args["by"])
        moved: dict[tuple[str, str], dict[str, tuple[float, float]]] = {}
        for kid in targets:
            owner, key = owner_of(ctx, kid), ctx.item(kid)
            old = timing.own_seconds(ctx, key, owner["id"])
            moved.setdefault((owner["id"], key["prop"]), {})[kid] = (old, around + (old - around) * by)
        for (owner_id, prop), mine in moved.items():
            final = {k["id"]: mine[k["id"]][1] if k["id"] in mine else timing.own_seconds(ctx, k, owner_id)
                     for k in keys_of(ctx.item(owner_id), prop)}
            ts = sorted(final.values())
            if any(b - a < 1e-6 for a, b in zip(ts, ts[1:])):
                ctx.fail(codes.CONFLICT, f"{owner_id}.{prop}", f"would have two keys at the same time after stretching by {by:g}",
                         hint="Stretch less, or move the other key first.")
            for kid, (old, new) in mine.items():
                key = ctx.item(kid)
                ctx.set(kid, "t", marked.moved(key["t"], new - old) if marked.marked(key) else round(new, 6))

    @registry.operation("key.paste", "Paste copies of keys onto the same settings of the target items, the first copied "
                        "key at `at` (the target's own seconds), the others keeping their spacing. Each key keeps its "
                        "value and ease. A target without one of those settings is refused, naming it.",
                        target=owners, label="Paste keys", importance="secondary",
                        params=[Param.list("from", "id", label="Keys", required=True, help="The keys to copy (their ids)"),
                                Param.number("at", label="At", min=-36000, max=36000, unit="s", required=True)])
    def key_paste(ctx, targets, args):
        src = []
        for kid in args["from"]:
            if kid not in index(ctx.doc, ctx.kind.lists) or ctx.item(kid).get("type") != "key":
                ctx.fail(codes.NOT_FOUND, f'from "{kid}"', "is not a key in this document", hint="Copy keys that still exist.")
            owner, key = owner_of(ctx, kid), dict(ctx.item(kid))
            src.append((timing.own_seconds(ctx, key, owner["id"]) + timing.offset(ctx, owner["id"]), key))
        first = min(t for t, _ in src)
        seen: set[tuple[str, str, float]] = set()
        for target in targets:
            for t, key in sorted(src, key=lambda x: x[0]):
                at = round(float(args["at"]) + t - first, 6)
                if (target, key["prop"], at) in seen:
                    ctx.fail(codes.CONFLICT, f'{target}.{key["prop"]}', f"would get two pasted keys at {at:g} s",
                             hint="Copy the keys of one item at a time.")
                seen.add((target, key["prop"], at))
                field = next(f for f in ("v", "c", "d") if f in key)
                put_key(ctx, target, key["prop"], at, {field: key_value(key), "ease": key.get("ease", "smooth")})
                made = next(k for k in keys_of(ctx.item(target), key["prop"]) if not marked.marked(k) and abs(k["t"] - at) < 1e-6)
                for name in SHAPING:
                    if name in key:
                        ctx.set(made["id"], name, key[name])

    register_key_stagger(registry, timing, orders)
