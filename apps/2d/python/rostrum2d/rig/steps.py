"""step() in a script: a few steps to a new place, one foot after the other, the body carried over them (guide
character-rigging-and-lip-sync, "Legs that act"). For a long walk across the frame use walk(); step() is for acting:
a step toward something, a step back in surprise, shifting where the character stands between lines.

    step(legs=[legL, legR], by=-120, at=6.0)          # two steps to the left, starting at 6 s, ~0.8 s long
    step(legs=[legL, legR], by=40, at=9.0, take=0.4)  # a quick small step right

Plain keys on the IK targets (the feet) and the body bone's moveX / moveY; each foot is planted except while it
swings, so the knees bend as the body passes over them. Keys already inside the step's span on those fields are
replaced; everything outside it stays.
"""
from __future__ import annotations

import math

from ..evaluate import value_at
from .limb import Limb


def maker(build, bone_of, Item):
    item = lambda node: Item(build, node)

    def step(legs, by, at, take=None, body=None, lead=None, lift=None, dip=None, ease="smooth"):
        """Move the character by `by` px (+ right) starting at `at` s, in side-steps (as a figure facing the camera
        moves; feet never cross): the lead foot (the one on that side, or `lead`) steps out, lifted `lift` px, the other
        follows to its place beside it, as many times as the legs need (each step at most 0.8 of a leg's length); the
        body travels over them and dips `dip` px at each step. `take`: seconds for it all (default 0.25 s a foot).
        Returns the time it ends. Seen from the side, use walk()."""
        legs = list(legs)
        if len(legs) != 2 or not all(isinstance(l, Limb) and l.ik is not None for l in legs):
            raise ValueError('step(legs=[left, right], by=px, at=s): two limbs made with limb(…, kind="leg")')
        by, at = float(by), float(at)
        if abs(by) < 1:
            raise ValueError(f"step: by={by} px moves nothing; give the distance to move (+ right, - left)")
        leg_len = legs[0].upper.node["length"] + legs[0].lower.node["length"]
        n = max(1, math.ceil(abs(by) / (0.8 * leg_len)))          # side-steps: 2 n swings, lead then trail
        take = float(take) if take is not None else 0.25 * 2 * n
        if take <= 0:
            raise ValueError(f"step: take {take} s must be above 0")
        lift = float(lift) if lift is not None else 0.12 * leg_len
        dip = float(dip) if dip is not None else 0.04 * leg_len
        body_n = bone_of(body)[1] if body is not None else bone_of(legs[0].upper.node["parent"])[1]
        first = legs.index(lead) if lead is not None else             max(range(2), key=lambda i: legs[i].upper.node["x"] * (1 if by > 0 else -1))
        order = [legs[first], legs[1 - first]]
        span, slot = (at, at + take), take / (2 * n)
        x0 = value_at(body_n, "moveX", at)
        _keys(item, body_n, "moveX", span, {at: x0, at + take: x0 + by}, ease)
        y0 = value_at(body_n, "moveY", at)
        bob = {at: y0, at + take: y0}
        for k in range(2 * n):
            bob[at + slot * (k + 0.5)] = y0 + dip                    # lowest as a foot passes under the body
        _keys(item, body_n, "moveY", span, bob, ease)
        start = {id(l): (value_at(l.ik.node, "targetX", at), value_at(l.ik.node, "targetY", at)) for l in legs}
        tx = {id(l): {} for l in legs}
        ty = {id(l): {} for l in legs}
        for k in range(2 * n):
            leg, j = order[k % 2], k // 2                         # swing k: step j of the lead (even k) or the trail
            fx, fy = start[id(leg)]
            a, b = at + slot * k, at + slot * (k + 1)
            tx[id(leg)].update({a: fx + by * j / n, b: fx + by * (j + 1) / n})
            ty[id(leg)].update({a: fy, (a + b) / 2: fy - lift, b: fy})
        for leg in legs:
            _keys(item, leg.ik.node, "targetX", span, tx[id(leg)], ease)
            _keys(item, leg.ik.node, "targetY", span, ty[id(leg)], ease)
        return at + take
    return step


def _keys(item, node, field, span, keys, ease):
    """Keys of `field` inside `span` replaced by `keys`."""
    node["keys"] = [k for k in node.get("keys", []) if not (k.get("prop") == field and isinstance(k["t"], (int, float))
                                                            and span[0] - 1e-9 <= k["t"] <= span[1] + 1e-9)]
    item(node).key(field, {round(t, 4): round(float(v), 3) for t, v in keys.items()}, ease=ease)
