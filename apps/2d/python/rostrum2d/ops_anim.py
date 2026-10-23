"""`anim.ease` (SPEC §9.4): set the ease of whole stretches in one change, one undo. A stretch is named by the keys it
starts at (anim.list gives them as a stretch's `ids`; for Position, X's and Y's key at that time). The ease lives on
those keys, as `key.set` / `key.handles` write it: this is their one-step form for a picked preset, a curve or a spring.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys import marked
from rostrum_core.tree import index

from .anims import PRESETS, setting_of
from .kind import REGISTRY as R

CURVE = ("x1", "y1", "x2", "y2")


@R.operation("anim.ease", "Ease whole stretches (the time between two keys of one setting) in one change: a preset "
             "(linear, smooth, in, out, spring, bounce, hold), or a curve (x1 y1 x2 y2, as CSS cubic-bezier: the ease "
             "becomes custom), or a spring's bounce and speed. Targets: the keys each stretch starts at (anim.list "
             "gives them as a stretch's ids). A setting's last key starts no stretch and is refused.",
             target="key", label="Ease", importance="secondary",
             params=[Param.choice("preset", list(PRESETS), label="Preset"),
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
    ease = "custom" if curve else "spring" if spring else PRESETS[args["preset"]]
    for kid in targets:
        _starts_stretch(ctx, kid)
        ctx.set(kid, "ease", ease)
        for n in (*curve, *spring):
            ctx.set(kid, n, args[n])


def _starts_stretch(ctx, kid: str):
    """Refuse a key after which its setting has no other key (X and Y of Position count together)."""
    owner = ctx.item(index(ctx.doc, ctx.kind.lists)[kid].parent)
    key = ctx.item(kid)
    if marked.marked(key) or any(marked.marked(k) for k in owner.get("keys", [])):
        return                                        # a marker's time needs the markers: accepted as written
    setting = setting_of(key["prop"])
    later = [k for k in owner.get("keys", []) if setting_of(k["prop"]) == setting and k["t"] > key["t"] + 1e-6]
    if not later:
        ctx.fail(codes.BAD_ARGUMENT, f'key "{kid}"', f"is the last key of {owner['id']}.{setting}: no stretch starts there",
                 hint="Give the key a stretch starts at (anim.list › stretches › ids).")

