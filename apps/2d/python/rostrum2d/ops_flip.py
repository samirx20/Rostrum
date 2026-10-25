"""`layer.flip`: mirror the picked layers across (left to right) or down (top to bottom), as Figma's Shift+H / Shift+V.
A flip is Stretch below 0 (fields.py lets Stretch X / Y go to −100 %), so it animates: a key at 100 % and one at −100 %
is a card flip. Width, height and Scale stay positive. Mirroring a layer across a line is, in its own frame, its
Stretch on that axis going negative and its turn going the other way, while its anchor point mirrors across the line
(`mirrored`; the canvas's resize past the opposite side uses the same rule, screen2d/group_slots.py). Fields are written
the way `value.set` does it: a still field changes, an animated one gets a key at `at`."""
from __future__ import annotations

from rostrum_core import Param

from . import boxes
from .evaluate import resolve
from .kind import REGISTRY as R
from .ops_align import AT, PLACED, _parent, _put

AXES = {"across": ("x", "scaleX"), "down": ("y", "scaleY")}


def mirrored(p: dict, across: bool, down: bool) -> dict:
    """The Stretch and turn a layer with values `p` takes when mirrored across and / or down (its place aside):
    one axis negates that Stretch and the turn; both is a half turn, so only the Stretches change. {} for neither."""
    out = {"scaleX": -p["scaleX"]} if across else {}
    out.update({"scaleY": -p["scaleY"]} if down else {})
    if across != down:
        out["rotation"] = -p["rotation"]
    return out


@R.operation("layer.flip", "Mirror layers: `axis` across (left to right) or down (top to bottom). `around` selection "
             "(the default: the picked layers' combined box's centre, so the arrangement mirrors as one picture) or each "
             "(every layer in its own place). Writes Stretch X or Y (below 0 is mirrored), rotation and position.",
             target=PLACED, label="Flip", importance="secondary",
             params=[Param.choice("axis", list(AXES), label="Axis", required=True,
                                  labels={"across": "Across", "down": "Down"}),
                     Param.choice("around", ["selection", "each"], label="Around"), AT])
def layer_flip(ctx, targets, args):
    t, axis = args.get("at", 0.0), args["axis"]
    pos, _ = AXES[axis]
    k = 0 if pos == "x" else 1
    if args.get("around", "selection") == "selection":
        _parent(ctx, targets)                                   # one parent, not placed by an auto layout
    items = {i: ctx.item(i) for i in targets}
    bx = {i: boxes.box(it, t) for i, it in items.items()}
    whole = (min(b[k] for b in bx.values()), max(b[k + 2] for b in bx.values()))
    for i, it in items.items():
        p = resolve(it, t)
        lo, hi = whole if args.get("around", "selection") == "selection" else (bx[i][k], bx[i][k + 2])
        if abs(lo + hi - 2 * p[pos]) > 1e-9:
            _put(ctx, i, pos, lo + hi - p[pos], args)          # its anchor mirrored across the centre line
        for prop, v in mirrored(p, axis == "across", axis == "down").items():
            if v != p[prop]:                                    # (no turn: nothing to write, no key)
                _put(ctx, i, prop, v, args)
