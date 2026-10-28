"""Script calls that make a limb in one go and write ordinary keys for walks, idles, follow-through and blinks
(guide character-rigging-and-lip-sync, "Limbs, walks and idles in a script"):

    with rig("kid", w=1200, h=1000):
        hip = bone("hip", x=600, y=560, angle=-90, length=0)
        chest = bone("chest", parent=hip, length=200)
        legL = limb("legL", parent=hip, x=580, y=560, lengths=(150, 140, 50), widths=(46, 40, 30), kind="leg")
        armL = limb("armL", parent=chest, x=560, y=380, lengths=(110, 100, 26), widths=(34, 30, 44))
        walk(legs=[legL, legR], arms=[armL, armR], body=hip, start=0.5, end=4.5, step=0.5, stride=110)
        idle(chest, head=neck, arms=[armL, armR], legs=[legL, legR], start=4.5)
        pose({armL: armL.out * 100, neck: 6}, at=6.0)   # a key pose: anticipation, overshoot, settle
        blink(eyes, open="eyes_open", closed="eyes_shut")
        shirt = layer("shirt")                    # an item made earlier in this script, by its id

Everything they make is plain: bones, an IK chain, shapes and binds a person edits as usual, and keys (sampled each
frame, then thinned to the few that draw the same curve within a fraction of a px or degree). Motion is written
inside `start`..`end` and blends in and out of what the bones already do there, so a re-run, a hand key before or
after, and a gesture on top all stay. At the end of the script a limb with no colour takes its body's, and an arm
without IK gets its elbow's natural bend from its upper bone's swing (`natural`), added to keys on its lower bone.
Sizes, colours and timing stay the caller's.
"""
from __future__ import annotations

import math

from rostrum_core.keys import key_id, keys_of

from ..evaluate import value_at
from ..ops_swap import blinks
from ..swap import child_index
from . import follow as follow_mod
from . import limb as limb_mod, limb_parts, steps
from .limb import PLACEHOLDER, Limb, bend_way
from .model import tip

SWING_BEND, SWING_TO, SWING_BACK = 1.5, 75.0, 55.0   # swung past SWING_TO degrees the bend is SWING_BEND x relax the way
                                                    # it swings (a raised arm's forearm up), back under SWING_BACK the rest
                                                    # bend again: a jump the spring eases, so no held pose is straight
NATURAL_LAG, NATURAL_OVER, NATURAL_DRAG = 0.1, 0.3, 0.6
TOL_PX, TOL_DEG, TOL_SCALE = 0.25, 0.15, 0.0005


def _rig_of(build):
    node = next((h for h in reversed(build.holders) if h["type"] == "rig"), None)
    if node is None:
        raise ValueError("limb(...) goes inside `with rig(...):`")
    return node


def _rig_holding(build, bone_id):
    stack = [build.root]
    while stack:
        n = stack.pop()
        if n.get("type") == "rig" and any(b["id"] == bone_id for b in n.get("bones", [])):
            return n
        stack += [c for v in n.values() if isinstance(v, list) for c in v if isinstance(c, dict)]
    raise ValueError(f'no bone "{bone_id}" was made earlier in this script (make it inside `with rig(...):` first)')


def _bone(build, ref):
    """A bone node from an Item, a Limb (its upper bone) or an id."""
    ref = ref.upper if isinstance(ref, Limb) else ref
    bid = getattr(ref, "id", ref)
    rig = _rig_holding(build, bid)
    return rig, next(b for b in rig["bones"] if b["id"] == bid)


def _comp(build):
    if not build.holders:
        raise ValueError("make a composition first: comp(...)")
    c = build.holders[0]
    return float(c.get("fps", 30)), float(c.get("duration", 5.0))


def for_script(build) -> dict:
    from ..script import Item

    def made(id_):
        stack = [build.root]
        while stack:
            n = stack.pop()
            if n.get("id") == id_ and n is not build.root:
                return n
            stack += [c for v in n.values() if isinstance(v, list) for c in v if isinstance(c, dict)]
        return None

    limbs, followed, walked = [], {}, {}   # what the end-of-script pass needs: limbs made, follow / walk ranges per bone

    def layer(id):
        """An item this script made earlier (layer, group, rig, bone, ik), found by its id."""
        node = made(id)
        if node is None:
            from rostrum_core.errors import did_you_mean
            ids_ = sorted(build.taken)
            hint = did_you_mean(id, ids_)
            raise ValueError(f'layer("{id}"): no item with that id was made earlier in this script.'
                             + (f" {hint}" if hint else "") + " A layer made outside this script is named by its id "
                             'where one is asked (bind(layer="leg", …)); to key it, make it in the script.')
        return Item(build, node)

    def limb(id, **kw):
        """Upper + lower (+ end) bones, an IK chain and plain shapes bound to them (rig/limb.py › make)."""
        return limb_mod.make(build, _rig_of(build), limbs, id, **kw)

    def follow(bone, start=0.0, end=None, lag=0.12, overshoot=0.4, amount=1.0):
        """rig.follow in a script: the bones below `bone` trail its turn (rotation keys, start .. end + the settle)."""
        rig, node = _bone(build, bone)
        fps, dur = _comp(build)
        end = dur if end is None else min(float(end), dur)
        if end <= start:
            raise ValueError(f"follow({node['id']}): end {end} s is not after start {start} s")
        if not follow_mod.descendants(rig["bones"], node["id"]):
            raise ValueError(f"follow({node['id']}): it has no bones below it to trail; pick the bone the motion starts at")
        span, baked = follow_mod.bake(rig["bones"], node["id"], fps, dur, float(start), end, lag, overshoot, amount)
        followed.setdefault(node["id"], []).append(span)
        bones = {b["id"]: b for b in rig["bones"]}
        for b, keys in baked.items():
            _write(bones[b], "rotation", span, keys)
        return Item(build, node)

    def blink(slot, open, closed, half=None, start=0.0, end=None, every=3.5, vary=0.3, seed=0, frames=2):
        """blink.add in a script: hold keys on a swap set's `show`; a time that already has a key keeps it."""
        node = made(getattr(slot, "id", slot))
        if node is None or not node.get("swap"):
            raise ValueError(f'blink: "{getattr(slot, "id", slot)}" must be a group made with swap=True earlier in this script')
        kids = [c["id"] for c in node["layers"]]
        pick = lambda w: child_index(kids, getattr(w, "id", w))
        o, c = pick(open), pick(closed)
        h = pick(half) if half is not None else None
        fps, dur = _comp(build)
        dt, end = 1 / fps, dur if end is None else float(end)
        plan = {round(float(start), 4): o}
        for b in blinks(float(start), end, every, vary, seed):
            if h is not None:
                plan[round(b - dt, 4)] = h
            plan[b] = c
            if h is not None:
                plan[round(b + frames * dt, 4)] = h
            plan[round(b + (frames + (h is not None)) * dt, 4)] = o
        have = {k["t"] for k in keys_of(node, "show")}
        Item(build, node).key("show", {t: (i, "hold") for t, i in plan.items() if t not in have})
        return sorted(t for t, i in plan.items() if i == c)

    def walk(legs, body=None, arms=(), head=None, start=0.0, end=None, step=0.5, stride=None, lift=None, bounce=None,
             travel=True, facing="right", swing=18.0, elbow=12.0, lean=3.0, toe=15.0, follow_through=True):
        """A walk: IK foot targets (planted feet, swing arcs), the body's bounce, lean and travel, arms swinging opposite
        the legs, as keys from `start` to `end` (then a half step to standing)."""
        legs = list(legs)
        if len(legs) != 2 or not all(isinstance(l, Limb) and l.ik is not None for l in legs):
            raise ValueError("walk(legs=[left, right]): two limbs made with limb(…, kind=\"leg\") (they have IK)")
        if facing not in ("right", "left"):
            raise ValueError(f'walk: facing "{facing}" is not right or left')
        fx = 1.0 if facing == "right" else -1.0
        for leg in legs:                     # knees point the way it walks
            leg.ik.node["bend"] = bend_way(leg.upper.node["angle"], facing, leg.id)
        fps, dur = _comp(build)
        start, end = float(start), dur if end is None else min(float(end), dur)
        if end <= start:
            raise ValueError(f"walk: end {end} s is not after start {start} s")
        rig, _ = _bone(build, legs[0].upper)
        bones = {b["id"]: b for b in rig["bones"]}
        body_n = _bone(build, body)[1] if body is not None else bones.get(legs[0].upper.node["parent"])
        if body_n is None:
            raise ValueError("walk: give body= (the hip bone the legs hang from)")
        leg_len = legs[0].upper.node["length"] + legs[0].lower.node["length"]
        S = float(stride) if stride is not None else 0.55 * leg_len
        lift_ = float(lift) if lift is not None else 0.12 * leg_len
        bnc = float(bounce) if bounce is not None else 0.04 * leg_len
        half = min(S / 2, 0.95 * leg_len)
        drop = leg_len - math.sqrt(max(leg_len ** 2 - half ** 2, 0.0)) + 0.02 * leg_len   # knees always a little bent
        period, ramp = 2 * float(step), 0.5 * float(step)
        last = min(dur, end + ramp)
        times = [start + i / fps for i in range(int(round((last - start) * fps)) + 1)]

        def env_in(t):
            return _smooth(min(1.0, (t - start) / ramp)) if ramp > 0 else 1.0

        def out_of(t):                       # 0 up to end, then 0 -> 1 over the ramp to standing
            return _smooth(min(1.0, max(0.0, (t - end) / ramp))) if ramp > 0 else float(t > end)

        def travel_at(t):
            return fx * S * (min(t, end) - start) / step if travel else 0.0

        def body_off(t):                     # moveX, moveY, rotation added to the body
            tt = min(t, end)
            p = ((tt - start) / step) % 1.0
            y = drop + bnc * (0.5 + 0.5 * math.cos(2 * math.pi * (p - 0.15)))
            r = fx * lean + 0.6 * math.sin(2 * math.pi * (tt - start) / period)
            k = 1 - out_of(t)
            return travel_at(t), y * k, r * k

        def foot(leg_i, t):                  # target x, y (rig px) and the foot's tilt
            leg = legs[leg_i]
            hx, ground = leg.upper.node["x"], tip(leg.lower.node)[1]
            tt = min(t, end)
            ph = ((tt - start) / period + 0.5 * leg_i) % 1.0
            if ph < 0.5:                     # on the ground, sliding back under the hip
                u = ph / 0.5
                rel, up, tilt = fx * (S / 2 - S * u), 0.0, 0.0
            else:
                u = (ph - 0.5) / 0.5
                rel = fx * S * (-0.5 + _smooth(u))
                up, tilt = lift_ * math.sin(math.pi * u), fx * toe * math.sin(2 * math.pi * u)
            x, y = hx + rel + travel_at(t), ground - up
            if t > end:                      # to standing under the hip where the walk ended
                k = out_of(t)
                x, y, tilt = x + k * (hx + travel_at(t) - x), y + k * (ground - y), tilt * (1 - k)
            return x, y, tilt

        own = {(n["id"], f): [float(value_at(n, f, t)) for t in times] for n in [body_n] for f in ("moveX", "moveY", "rotation")}
        tracks = {}
        for f, i in (("moveX", 0), ("moveY", 1), ("rotation", 2)):
            tracks[(body_n["id"], f)] = [o + env_in(t) * body_off(t)[i] for o, t in zip(own[(body_n["id"], f)], times)]
        for li, leg in enumerate(legs):
            ikn = leg.ik.node
            cur = {f: [float(value_at(ikn, f, t)) for t in times] for f in ("targetX", "targetY")}
            xs, ys, tilts = zip(*(foot(li, t) for t in times))
            tracks[(ikn["id"], "targetX")] = [c + env_in(t) * (v - c) for c, v, t in zip(cur["targetX"], xs, times)]
            tracks[(ikn["id"], "targetY")] = [c + env_in(t) * (v - c) for c, v, t in zip(cur["targetY"], ys, times)]
            if leg.end is not None:          # the foot kept flat on the ground (against the shin's turn), tilted in the swing
                en = leg.end.node
                own_f = [float(value_at(en, "rotation", t)) for t in times]
                flat = []
                for t, x, y, tl in zip(times, tracks[(ikn["id"], "targetX")], tracks[(ikn["id"], "targetY")], tilts):
                    off = body_off(t)
                    shin = _shin_turn(body_n, leg, (off[0] * env_in(t), off[1] * env_in(t), off[2] * env_in(t)), (x, y))
                    flat.append(env_in(t) * (-shin + tl))
                tracks[(en["id"], "rotation")] = [o + v for o, v in zip(own_f, flat)]
                walked.setdefault(en["id"], []).append((times[0], times[-1]))
        for ai, arm in enumerate(list(arms)[:2]):
            for n, fn in ((arm.upper.node, lambda ph: fx * swing * math.cos(2 * math.pi * ph)),
                          (arm.lower.node, lambda ph: -fx * elbow * (1 + 0.6 * max(0.0, -math.cos(2 * math.pi * ph))))):
                own_a = [float(value_at(n, "rotation", t)) for t in times]
                vals = []
                for o, t in zip(own_a, times):
                    ph = ((min(t, end) - start) / period + 0.5 * ai) % 1.0
                    vals.append(o + env_in(t) * (1 - out_of(t)) * fn(ph))
                tracks[(n["id"], "rotation")] = vals
        if head is not None:
            hn = _bone(build, head)[1]
            own_h = [float(value_at(hn, "rotation", t)) for t in times]
            tracks[(hn["id"], "rotation")] = [o - env_in(t) * body_off(t)[2] * 0.6 for o, t in zip(own_h, times)]
        nodes = {b["id"]: b for b in rig["bones"]} | {i["id"]: i for i in rig["iks"]}
        span = (times[0], times[-1])
        for (nid, f), vals in tracks.items():
            _write(nodes[nid], f, span, _thinned(times, vals, f))
        if follow_through:
            for arm in list(arms)[:2]:
                follow(arm.upper, start, end, lag=0.08, overshoot=0.35, amount=0.8)
        return {"steps": int((end - start) / step), "stride": round(S, 1), "travel": round(travel_at(end), 1)}

    def idle(body, head=None, arms=(), legs=(), start=0.0, end=None, breath=3.5, amount=1.0, seed=0, follow_through=True,
             weight=True, shift=None):
        """Breathing and weight shift on top of what the bones do: the chest bone's scale and sway, a slow head drift,
        shoulders rising with each breath; every breath a little different (seeded). With legs (two leg limbs) the hip
        sways from foot to foot by `shift` px and sinks, so the knees bend in turn while the feet stay planted."""
        rig, bn = _bone(build, body)
        fps, dur = _comp(build)
        start, end = float(start), dur if end is None else min(float(end), dur)
        if end <= start:
            raise ValueError(f"idle: end {end} s is not after start {start} s")
        rnd = _Rand(seed)
        ramp = min(0.4, (end - start) / 3)
        times = [start + i / fps for i in range(int(round((end - start) * fps)) + 1)]
        beats, t = [start], start                       # breath starts, each 85..115 % of `breath`
        while t < end:
            t += breath * (0.85 + 0.3 * rnd())
            beats.append(t)
        ph_head, ph_sway = rnd() * 6.28, rnd() * 6.28

        def breath_at(t):                               # 0 (out) .. 1 (in): a quicker in, a slower out
            i = max(j for j, b in enumerate(beats) if b <= t + 1e-9) if t >= beats[0] else 0
            a, b = beats[i], beats[min(i + 1, len(beats) - 1)]
            u = (t - a) / (b - a) if b > a else 0.0
            return _smooth(u / 0.4) if u < 0.4 else 1 - _smooth((u - 0.4) / 0.6)

        def env(t):
            return _smooth(min(1.0, (t - start) / ramp, (end - t) / ramp)) if ramp > 0 else 1.0

        sway = lambda t: 0.8 * amount * math.sin(2 * math.pi * (t - start) / (breath * 2.3) + ph_sway)
        tracks = [(bn, "scale", lambda t: 0.012 * amount * breath_at(t)), (bn, "rotation", sway)]
        if head is not None:            # drifts on its own, and keeps the eyes level against the body's sway
            tracks.append((_bone(build, head)[1], "rotation",
                           lambda t: 1.5 * amount * math.sin(2 * math.pi * (t - start) / (breath * 1.7) + ph_head) - sway(t)))
        for arm in list(arms)[:2]:                      # shoulders rise with the breath, each arm outward
            out = arm.out if isinstance(arm, Limb) else 1
            tracks.append((_bone(build, arm)[1], "rotation", (lambda s: lambda t: s * 1.2 * amount * breath_at(t))(out)))
        legs = [l for l in legs if isinstance(l, Limb)]
        if weight and len(legs) == 2:                   # weight from foot to foot: the hip slides over one, sinks a little
            hip = _bone(build, legs[0].upper.node["parent"])[1]
            leg_len = legs[0].upper.node["length"] + legs[0].lower.node["length"]
            px = float(shift) if shift is not None else 0.035 * leg_len
            per = breath * 2.3 * 1.9
            ph_w = rnd() * 6.28
            side = lambda t: math.sin(2 * math.pi * (t - start) / per + ph_w)
            tracks += [(hip, "moveX", lambda t: amount * px * side(t)),
                       (hip, "moveY", lambda t: amount * (0.012 * leg_len + 0.01 * leg_len * abs(side(t)))),
                       (hip, "rotation", lambda t: -amount * 1.2 * side(t))]
            for leg in legs:                            # an FK leg bends its knee when the weight leaves it
                if leg.ik is None:
                    away = (lambda s: lambda t: max(0.0, s * side(t)))(1 if leg.upper.node["x"] < hip["x"] else -1)
                    k = next(r["sign"] for r in limbs if r["limb"] is leg)
                    tracks += [(leg.lower.node, "rotation", (lambda a, k: lambda t: k * 8 * amount * a(t))(away, k)),
                               (leg.upper.node, "rotation", (lambda a, k: lambda t: -k * 4 * amount * a(t))(away, k))]
        span = (times[0], times[-1])
        for n, f, fn in tracks:
            own = [float(value_at(n, f, t)) for t in times]
            _write(n, f, span, _thinned(times, [o + env(t) * fn(t) for o, t in zip(own, times)], f))
        if follow_through:
            for arm in list(arms)[:2]:
                follow(arm.upper, start, end, lag=0.15, overshoot=0.3, amount=1.0)
        return {"breaths": len(beats) - 1}

    def pose(targets, at, take=0.5, anticipate=0.12, overshoot=0.1, settle=0.35, stagger=0.04, ease="smooth"):
        """Several bones to a key pose at `at` together: each eases from where it is `take` s before, pulls back by
        `anticipate` of the move first, swings past by `overshoot` and settles `settle` s later; each next entry
        lands `stagger` s later (overlap). targets: {limb or bone: turn} or {bone: {field: value}} or
        {limb: {"upper": a, "lower": b, "end": c}}."""
        at, take = float(at), float(take)
        if take <= 0:
            raise ValueError(f"pose: take {take} s must be above 0")
        if not isinstance(targets, dict) or not targets:
            raise ValueError('pose({armR: -100, neck: {"rotation": 8}}, at=4): a dict of limb or bone -> value')
        for i, (who, v) in enumerate(targets.items()):
            if isinstance(who, Limb):
                parts = v.items() if isinstance(v, dict) else (("upper", v),)
                bad = [k for k, _ in parts if k not in ("upper", "lower", "end") or getattr(who, k) is None]
                fields = [(getattr(who, k).node, "rotation", a) for k, a in parts if k not in bad]
            else:
                node = _bone(build, who)[1]
                fields = [(node, f, a) for f, a in (v.items() if isinstance(v, dict) else (("rotation", v),))]
                bad = [f for _, f, _ in fields if f not in ("rotation", "moveX", "moveY", "scale")]
            if bad:
                raise ValueError(f"pose: {getattr(who, 'id', who)} has no {', '.join(bad)} to pose "
                                 "(a limb: upper, lower, end; a bone: rotation, moveX, moveY, scale)")
            land = at + i * stagger
            for node, f, v1 in fields:
                t0, v1 = land - take, float(v1)
                v0 = float(value_at(node, f, t0))
                d = v1 - v0
                keys = [(t0, v0)]
                if anticipate and abs(d) > 1e-6:
                    keys.append((t0 + 0.45 * take, v0 - anticipate * d))
                keys.append((land, v1 + overshoot * d))
                if overshoot and settle > 0:
                    keys.append((land + settle, v1))
                node["keys"] = [k for k in node.get("keys", []) if not (k.get("prop") == f and isinstance(k["t"], (int, float))
                                                                        and t0 + 1e-9 < k["t"] <= keys[-1][0] + 1e-9)]
                Item(build, node).key(f, {round(t, 4): round(v, 3) for t, v in keys}, ease=ease)
        return at + (len(targets) - 1) * stagger + settle

    def natural():
        """The end of the script: limbs made with no widths are sized to their body; limbs left in the placeholder colour
        take their body's; each arm without IK gets its elbow bend following the upper bone's swing (a lagging spring), and drag where follow() did not run."""
        if not build.holders or not limbs:
            return
        fps, dur = _comp(build)
        times = [i / fps for i in range(int(round(dur * fps)) + 1)]
        turns = {}                                      # a bone's turn per frame, sampled once (shared parents)
        limb_mod.fit_widths(limbs)                      # widths=None: the limbs sized to their body

        def turn(node):
            if node["id"] not in turns:
                turns[node["id"]] = [float(value_at(node, "rotation", t)) for t in times]
            return turns[node["id"]]
        for rec in limbs:
            lm, rig = rec["limb"], rec["rig"]
            if rec["auto_color"] and all(p.node.get("fill") == PLACEHOLDER for p in lm.parts):
                col = _body_color(rig, lm.upper.node["parent"], {p.node["id"] for p in lm.parts})
                for p in lm.parts:
                    p.node["fill"] = col
            if rec["outline"] is not False:             # after the colour is known; a part given its own outline keeps it
                limb_parts.outline_parts([p for p in lm.parts if not p.node.get("stroke")], rec["outline"], limb_mod.line_width(rec))
            if lm.ik is not None and lm.kind == "leg" and lm.end is not None:
                _flat_foot(lm, rig, times, walked.get(lm.end.node["id"], []))
            if not rec["natural"]:
                continue
            up, lo, en = lm.upper.node, lm.lower.node, lm.end.node if lm.end else None
            bones = {b["id"]: b for b in rig["bones"]}
            rest_u = float(up.get("rotation", 0.0))
            rlx, sgn = rec["relax"], rec["sign"]
            delta = [v - rest_u for v in turn(up)]

            bend = follow_mod.spring(_swing_bends(delta, sgn * rlx), 1 / fps, NATURAL_LAG, NATURAL_OVER)
            own_lo = [float(value_at(lo, "rotation", t)) if keys_of(lo, "rotation") else 0.0 for t in times]
            mask = _outside(times, followed.get(up["id"], []), 0.25)
            drive, bid = [0.0] * len(times), up["id"]   # the upper bone's turn on screen: its own plus its parents' (FK)
            while bid in bones:
                drive = [d + v for d, v in zip(drive, turn(bones[bid]))]
                bid = bones[bid]["parent"]
            drag_lo = [NATURAL_DRAG * m * (y - x) for m, y, x in zip(mask, follow_mod.spring(drive, 1 / fps, NATURAL_LAG, 0.35), drive)]
            new_lo = [o + b + g for o, b, g in zip(own_lo, bend, drag_lo)]
            if max(new_lo) - min(new_lo) > TOL_DEG:
                _write(lo, "rotation", (0.0, dur), _thinned(times, new_lo, "rotation"))
            else:
                lo["keys"] = [k for k in lo.get("keys", []) if k.get("prop") != "rotation"]
                lo["rotation"] = round(new_lo[0], 3)
            if en is not None:
                drive2 = [d + l for d, l in zip(drive, new_lo)]
                drag_en = [NATURAL_DRAG * m * (y - x) for m, y, x in zip(mask, follow_mod.spring(drive2, 1 / fps, 2 * NATURAL_LAG, 0.35), drive2)]
                if max(map(abs, drag_en)) > TOL_DEG:
                    own_en = [float(value_at(en, "rotation", t)) for t in times]
                    _write(en, "rotation", (0.0, dur), _thinned(times, [o + g for o, g in zip(own_en, drag_en)], "rotation"))

    if not hasattr(build, "finishers"):
        build.finishers = []
    build.finishers.append(natural)
    return {"layer": layer, "limb": limb, "follow": follow, "blink": blink, "walk": walk, "idle": idle, "pose": pose,
            "step": steps.maker(build, lambda ref: _bone(build, ref), Item)}


def _swing_bends(delta: list[float], rest: float) -> list[float]:
    """The elbow's bend per frame from the upper bone's swing: `rest` (the forearm hanging), turned to SWING_BEND x it the
    way the arm swings once swung past SWING_TO, until it comes back under SWING_BACK (two thresholds: no flicker)."""
    out, up = [], False
    for dl in delta:
        up = abs(dl) >= (SWING_BACK if up else SWING_TO)
        out.append(math.copysign(SWING_BEND * abs(rest), dl) if up else rest)
    return out


def _smooth(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


class _Rand:
    def __init__(self, seed):
        import random
        self.r = random.Random(seed)

    def __call__(self):
        return self.r.random()


def _outside(times, spans, ramp):
    """1 away from every span, 0 inside one, a smooth ramp of `ramp` s at its edges."""
    out = []
    for t in times:
        m = 1.0
        for a, b in spans:
            d = max(a - t, t - b, 0.0)
            m = min(m, _smooth(d / ramp) if ramp > 0 else float(d > 0))
        out.append(m)
    return out


def _body_color(rig: dict, bone_id: str, skip: set) -> str:
    """The fill of the largest plain-coloured layer bound to this bone or the nearest bone above it that has one."""
    bones = {b["id"]: b for b in rig["bones"]}
    layers, stack = {}, list(rig.get("layers", []))
    while stack:
        n = stack.pop()
        layers[n.get("id")] = n
        stack += n.get("layers", [])
    while bone_id:
        best = None
        for b in rig.get("binds", []):
            n = layers.get(b.get("layer"))
            if b.get("bone") != bone_id or n is None or n["id"] in skip:
                continue
            fill = n.get("fill")
            if isinstance(fill, str) and fill.startswith("#") and float(n.get("opacity", 1)) > 0.5:
                area = float(n.get("w", 0) or 0) * float(n.get("h", 0) or 0)
                best = max(best or (area, fill), (area, fill))
        if best:
            return best[1]
        bone_id = bones.get(bone_id, {}).get("parent")
    return PLACEHOLDER


def _thinned(times, values, field):
    tol = TOL_DEG if field == "rotation" else TOL_SCALE if field == "scale" else TOL_PX
    values = [round(v, 4) for v in values]
    return [(round(times[i], 4), values[i]) for i in follow_mod.thin(times, values, tol)]


def _write(node: dict, field: str, span, keys):
    """Keys of `field` inside `span` replaced by `keys` (linear), on a script's node: a re-run merges key by key."""
    node["keys"] = [k for k in node.get("keys", []) if not (k.get("prop") == field and isinstance(k["t"], (int, float))
                                                            and span[0] - 1e-9 <= k["t"] <= span[1] + 1e-9)]
    for t, v in keys:
        node["keys"].append({"id": key_id(node["id"], field, t), "type": "key", "prop": field, "t": float(t), "v": v, "ease": "linear"})


def _flat_foot(leg: Limb, rig: dict, times, walked) -> None:
    """An IK leg's foot kept flat (its rest direction on screen) however the body crouches, steps or leans: the shin's
    turn taken off the foot bone's own keys, frame by frame, except where walk() already wrote it."""
    bones = {b["id"]: b for b in rig["bones"]}
    body, ik, en = bones.get(leg.upper.node["parent"]), leg.ik.node, leg.end.node
    if body is None or (not keys_of(body, "moveX") and not keys_of(body, "moveY") and not keys_of(body, "rotation")
                        and not keys_of(ik, "targetX") and not keys_of(ik, "targetY")):
        return
    mask = _outside(times, walked, 0.2)
    flat = [m * -_shin_turn(body, leg, tuple(float(value_at(body, f, t)) for f in ("moveX", "moveY", "rotation")),
                            (float(value_at(ik, "targetX", t)), float(value_at(ik, "targetY", t))))
            for m, t in zip(mask, times)]
    if max(map(abs, flat)) <= TOL_DEG:
        return
    own = [float(value_at(en, "rotation", t)) for t in times]
    _write(en, "rotation", (times[0], times[-1]), _thinned(times, [o + v for o, v in zip(own, flat)], "rotation"))


def _shin_turn(body: dict, leg: Limb, off, target) -> float:
    """The lower bone's turn from rest (degrees) when the two-bone IK reaches `target`, the body moved by `off`
    (moveX, moveY, rotation): the same solve the engine makes (RIG.md § Evaluation, step 2)."""
    u, l = leg.upper.node, leg.lower.node
    r = math.radians(off[2])
    dx, dy = u["x"] - body["x"], u["y"] - body["y"]
    px = body["x"] + off[0] + dx * math.cos(r) - dy * math.sin(r)
    py = body["y"] + off[1] + dx * math.sin(r) + dy * math.cos(r)
    a, b = u["length"], l["length"]
    tx, ty = target[0] - px, target[1] - py
    d = min(max(math.hypot(tx, ty), abs(a - b) + 1e-6), a + b - 1e-6)
    base = math.atan2(ty, tx)
    inner = math.acos(max(-1.0, min(1.0, (a * a + d * d - b * b) / (2 * a * d))))
    sign = -1.0 if leg.ik.node.get("bend", "clockwise") == "clockwise" else 1.0
    ua = base + sign * inner
    kx, ky = px + a * math.cos(ua), py + a * math.sin(ua)
    lower_world = math.degrees(math.atan2(target[1] - ky, target[0] - kx))
    turn = lower_world - l["angle"]
    return (turn + 180) % 360 - 180
