"""Follow-through and overlapping action (`rig.follow`): the bones below a bone lag behind its turn, swing past and
settle, the way an arm trails a body or a tail trails a hip. Each bone below the target follows its parent's turn (the
parent's direction on screen) through a spring, and each step out lags a little more, so the chain whips instead of
turning as one stiff piece. It is baked: ordinary `rotation` keys on those bones over a time range (plus the settle
after it), added on top of the bone's own motion, so a person edits them like any keys and a second run re-bakes the
range. The target bone itself is not changed. Only keys are put; nothing else on the rig changes."""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys import keys_of
from rostrum_core.tree import index

from ..evaluate import value_at
from ..kind import REGISTRY as R
from ..ops_keys import put_key
from .joints import rig_of

TOLERANCE = 0.15                                # degrees: a baked curve drops keys it can be drawn without
SUBSTEPS = 8


def descendants(bones: list, root: str) -> list[list[str]]:
    """Ids of the bones below `root`, one list per step out (children, grandchildren, ...)."""
    steps, level = [], [root]
    while True:
        level = [b["id"] for b in bones if b["parent"] in level]
        if not level:
            return steps
        steps.append(level)


def spring(drive: list[float], dt: float, lag: float, overshoot: float) -> list[float]:
    """`drive` followed by a spring that catches up in about `lag` seconds; overshoot 0 = no swing past, 1 = a long wobble."""
    w, z = 2.0 / max(lag, 1e-3), 1.0 - 0.85 * overshoot
    y, v, out = drive[0], 0.0, []
    for i, x in enumerate(drive):
        nxt = drive[min(i + 1, len(drive) - 1)]
        for s in range(SUBSTEPS):
            target = x + (nxt - x) * s / SUBSTEPS
            v += (w * w * (target - y) - 2 * z * w * v) * dt / SUBSTEPS
            y += v * dt / SUBSTEPS
        out.append(y)
    return out


def thin(times: list[float], values: list[float], tol: float) -> list[int]:
    """Indexes of the samples worth a key: a straight line between the kept ones stays within `tol` (Ramer-Douglas-Peucker)."""
    keep, stack = {0, len(times) - 1}, [(0, len(times) - 1)]
    while stack:
        a, b = stack.pop()
        worst, at = 0.0, None
        for i in range(a + 1, b):
            line = values[a] + (values[b] - values[a]) * (times[i] - times[a]) / (times[b] - times[a])
            if abs(values[i] - line) > worst:
                worst, at = abs(values[i] - line), i
        if at is not None and worst > tol:
            keep.add(at)
            stack += [(a, at), (at, b)]
    return sorted(keep)


def comp_of(ctx, id_: str) -> dict:
    """The scene that holds this item."""
    idx = index(ctx.doc, ctx.kind.lists)
    loc = idx[id_]
    while loc.item["type"] != "comp":
        loc = idx[loc.parent]
    return loc.item


@R.operation("rig.follow", "Follow-through for a chain: the bones below this bone lag behind its turn, swing past and settle "
             "(an arm trailing a body, a tail, hair), each step out a little later. Baked as editable `rotation` keys on "
             "those bones from `start` to `end` plus the settle; the bone itself is untouched. `lag` is how long a "
             "bone takes to catch up its parent (s), `overshoot` how far it swings past (0 none, 1 a long wobble), "
             "`amount` how much of the lag shows (0 none, 1 all).", target="bone", label="Follow through",
             params=[Param.number("start", label="From", default=0.0, min=0, max=36000, unit="s"),
                     Param.number("end", label="To", min=0, max=36000, unit="s",
                                  help="End of the motion that drives it; empty = the end of the scene"),
                     Param.number("lag", label="Lag", default=0.12, min=0.02, max=5, unit="s", step=0.01,
                                  help="Each step out down the chain lags this much more"),
                     Param.number("overshoot", label="Swing past", default=0.4, min=0, max=1, step=0.05),
                     Param.number("amount", label="Amount", default=1.0, min=0, max=1, step=0.05)])
def rig_follow(ctx, targets, args):
    for t in targets:
        rig = rig_of(ctx, t)
        bones = {b["id"]: b for b in rig["bones"]}
        steps = descendants(rig["bones"], t)
        if not steps:
            ctx.fail(codes.BAD_ARGUMENT, t, "has no bones below it to follow through",
                     hint="Pick the bone the motion starts at (the upper arm, the hip); its children are the ones that trail.")
        comp = comp_of(ctx, t)
        fps, comp_end = float(comp.get("fps", 30)), float(comp.get("duration", 5.0))
        lag, over, amount = args.get("lag", 0.12), args.get("overshoot", 0.4), args.get("amount", 1.0)
        start, end = args.get("start", 0.0), min(args.get("end", comp_end), comp_end)
        if end <= start:
            ctx.fail(codes.BAD_ARGUMENT, "end", f"{end} s is not after start {start} s")
        last = min(comp_end, end + 4 * lag * len(steps))                 # room for the tail to settle
        times = [start + i / fps for i in range(int(round((last - start) * fps)) + 1)]
        own = {b: [float(value_at(bones[b], "rotation", s)) for s in times] for b in bones}
        world = {}                                                       # each bone's turn on screen, per sample
        for b in _top_down(bones):
            up = world.get(bones[b]["parent"], [0.0] * len(times))
            world[b] = [u + o for u, o in zip(up, own[b])]
        for n, level in enumerate(steps, 1):
            for b in level:
                drive = world[bones[b]["parent"]]                        # the parent, already followed
                lagged = spring(drive, 1 / fps, lag * n, over)
                own[b] = [o + amount * (y - x) for o, y, x in zip(own[b], lagged, drive)]
                world[b] = [d + o for d, o in zip(drive, own[b])]
            for b in level:
                values = [round(v, 3) for v in own[b]]
                for k in [k for k in keys_of(bones[b], "rotation") if times[0] - 1e-9 <= k["t"] <= times[-1] + 1e-9]:
                    ctx.remove(k["id"])
                for i in thin(times, values, TOLERANCE):
                    put_key(ctx, b, "rotation", round(times[i], 4), {"v": values[i], "ease": "linear"})


def _top_down(bones: dict) -> list[str]:
    out, todo = [], list(bones)
    while todo:
        nxt = [b for b in todo if bones[b]["parent"] not in bones or bones[b]["parent"] in out]
        out += nxt
        todo = [b for b in todo if b not in nxt]
    return out
