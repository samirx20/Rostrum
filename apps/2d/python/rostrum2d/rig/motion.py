"""Script calls that make a limb in one go and write ordinary keys for walks, idles, follow-through and blinks
(guide character-rigging-and-lip-sync, "Limbs, walks and idles in a script"):

    with rig("kid", w=1200, h=1000):
        hip = bone("hip", x=600, y=560, angle=-90, length=0)
        chest = bone("chest", parent=hip, length=200)
        legL = limb("legL", parent=hip, x=580, y=560, lengths=(150, 140, 50), widths=(46, 40, 30), kind="leg")
        armL = limb("armL", parent=chest, x=560, y=380, lengths=(110, 100, 26), widths=(34, 30, 44))
        walk(legs=[legL, legR], arms=[armL, armR], body=hip, start=0.5, end=4.5, step=0.5, stride=110)
        idle(chest, head=neck, arms=[armL, armR], start=4.5)
        blink(eyes, open="eyes_open", closed="eyes_shut")
        shirt = layer("shirt")                    # an item made earlier in this script, by its id

Everything they make is plain: bones, an IK chain, shapes and binds a person edits as usual, and keys (sampled each
frame, then thinned to the few that draw the same curve within a fraction of a px or degree). Motion is written
inside `start`..`end` and blends in and out of what the bones already do there, so a re-run, a hand key before or
after, and a gesture on top all stay. Nothing here chooses a look: sizes, colours and timing are the caller's.
"""
from __future__ import annotations

import math

from rostrum_core.keys import key_id, keys_of

from ..evaluate import value_at
from ..ops_swap import blinks
from ..swap import child_index
from . import follow as follow_mod
from .model import start_bone, tip

LIMB_KINDS = ("arm", "leg")
PIECES = ("bend", "parts", "none")
TOL_PX, TOL_DEG, TOL_SCALE = 0.25, 0.15, 0.0005


class Limb:
    """What limb() made: `upper`, `lower`, `end` (bones; `end` is None with no third length), `ik` (the chain on the
    lower bone, or None), `parts` (the shapes). `reach({t: (x, y)})` keys the IK target in rig px."""

    def __init__(self, id_, kind, upper, lower, end, ik, parts):
        self.id, self.kind, self.upper, self.lower, self.end, self.ik, self.parts = id_, kind, upper, lower, end, ik, parts

    def reach(self, keys: dict, ease: str = "smooth") -> "Limb":
        if self.ik is None:
            raise ValueError(f"{self.id}.reach(…): this limb has no IK chain; make it with limb(…, ik=True)")
        xs, ys = {}, {}
        for t, v in keys.items():
            (x, y), e = (v[0], v[1] if len(v) > 1 else ease) if isinstance(v[0], (tuple, list)) else (v, ease)
            xs[t], ys[t] = (x, e), (y, e)
        self.ik.key("targetX", xs).key("targetY", ys)
        return self

    def __repr__(self):
        return f"limb {self.id} ({self.kind}: {self.upper.id} › {self.lower.id}{' › ' + self.end.id if self.end else ''})"


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

    def limb(id, x=None, y=None, angle=90, lengths=(120, 110, 30), widths=(40, 34, 44), parent=None, kind="arm",
             ik=None, bend="right", pieces="bend", color="#d9d9d9", end_color=None, end_angle=None, soft=None):
        """Upper + lower (+ end: hand / foot) bones from (x, y) along `angle`, an IK chain on the lower bone, and
        plain shapes bound to them. Legs get IK by default, arms don't (key their turns, or pass ik=True)."""
        rig = _rig_of(build)
        if kind not in LIMB_KINDS:
            raise ValueError(f'limb {id}: kind "{kind}" is not one of {", ".join(LIMB_KINDS)}')
        if pieces not in PIECES:
            raise ValueError(f'limb {id}: pieces "{pieces}" is not one of {", ".join(PIECES)}')
        lens = tuple(float(v) for v in lengths) + (0.0,) * (3 - len(lengths))
        wid = tuple(float(v) for v in widths) + (widths[-1],) * (3 - len(widths))
        if lens[0] <= 0 or lens[1] <= 0:
            raise ValueError(f"limb {id}: the first two lengths (upper, lower) must be above 0, not {lengths}")
        pid = getattr(parent.upper if isinstance(parent, Limb) else parent, "id", parent) or ""
        start = start_bone(rig["bones"], {"parent": pid, **({"x": x} if x is not None else {}), **({"y": y} if y is not None else {})})
        if "x" not in start or "y" not in start:
            raise ValueError(f"limb {id}: give x, y (the shoulder or hip joint, rig px), or a parent to start at its tip")
        bx, by = float(start["x"]), float(start["y"])
        # the bone calls, as a script writes them (script.for_script: bone / ik / bind)
        from .script import for_script as rig_calls
        calls = rig_calls(build)
        upper = calls["bone"](f"{id}_upper", parent=pid, x=bx, y=by, angle=angle, length=lens[0])
        lower = calls["bone"](f"{id}_lower", parent=upper, length=lens[1])
        ea = end_angle if end_angle is not None else (0.0 if kind == "leg" else angle)
        end = calls["bone"](f"{id}_end", parent=lower, angle=ea, length=lens[2]) if lens[2] > 0 else None
        chain = calls["ik"](f"{id}_ik", bone=lower, bend=bend_way(angle, bend, id)) if (ik if ik is not None else kind == "leg") else None
        parts = []
        a = math.radians(angle)
        ux, uy = math.cos(a), math.sin(a)

        def bar(pid_, length, w, at, col):
            cx, cy = bx + ux * at, by + uy * at
            return build.layer("shape", pid_, shape="rect", x=cx, y=cy, w=w, h=length + w, radius=w / 2,
                               rotation=angle - 90, fill=col)

        if pieces == "bend":
            p = bar(id, lens[0] + lens[1], wid[0], (lens[0] + lens[1]) / 2, color)
            calls["bind"](layer=p, bone=upper, bone2=lower, soft=soft if soft is not None else max(wid[0], 12.0))
            parts.append(p)
        elif pieces == "parts":
            for bone_, n, w, at in ((upper, lens[0], wid[0], lens[0] / 2), (lower, lens[1], wid[1], lens[0] + lens[1] / 2)):
                p = bar(f"{bone_.id}_part", n, w, at, color)
                calls["bind"](layer=p, bone=bone_)
                parts.append(p)
        if pieces != "none" and end is not None:
            wx, wy = tip(lower.node)
            e = math.radians(ea)
            col = end_color or color
            if kind == "leg":
                p = build.layer("shape", f"{id}_foot", shape="rect", x=wx + math.cos(e) * lens[2] / 2, y=wy + math.sin(e) * lens[2] / 2,
                                w=lens[2] + wid[2], h=wid[2], radius=wid[2] / 2, rotation=ea, fill=col)
            else:
                p = build.layer("shape", f"{id}_hand", shape="ellipse", x=wx + math.cos(e) * lens[2] * 0.5,
                                y=wy + math.sin(e) * lens[2] * 0.5, w=wid[2], h=wid[2], fill=col)
            calls["bind"](layer=p, bone=end)
            parts.append(p)
        return Limb(id, kind, upper, lower, end, chain, parts)

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

    def idle(body, head=None, arms=(), start=0.0, end=None, breath=3.5, amount=1.0, seed=0, follow_through=True):
        """Breathing and weight shift on top of what the bones do: the chest bone's scale and sway, a slow head drift,
        shoulders rising with each breath; every breath a little different (seeded)."""
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
        for i, arm in enumerate(list(arms)[:2]):        # shoulders rise with the breath, each arm outward
            tracks.append((arm.upper.node, "rotation", (lambda s: lambda t: s * 1.2 * amount * breath_at(t))(1 if i == 0 else -1)))
        span = (times[0], times[-1])
        for n, f, fn in tracks:
            own = [float(value_at(n, f, t)) for t in times]
            _write(n, f, span, _thinned(times, [o + env(t) * fn(t) for o, t in zip(own, times)], f))
        if follow_through:
            for arm in list(arms)[:2]:
                follow(arm.upper, start, end, lag=0.15, overshoot=0.3, amount=1.0)
        return {"breaths": len(beats) - 1}

    return {"layer": layer, "limb": limb, "follow": follow, "blink": blink, "walk": walk, "idle": idle}


SIDES = {"right": 0.0, "down": 90.0, "left": 180.0, "up": 270.0}


def bend_way(angle: float, bend: str, where: str) -> str:
    """An IK bend: clockwise / counterclockwise as given, or the screen side the joint should point to (left, right,
    up, down) for a limb whose rest direction is `angle` (clockwise puts the joint at angle - 90)."""
    if bend in ("clockwise", "counterclockwise"):
        return bend
    if bend not in SIDES:
        raise ValueError(f'limb {where}: bend "{bend}" is not one of clockwise, counterclockwise, {", ".join(SIDES)}')
    return "clockwise" if math.cos(math.radians(angle - 90 - SIDES[bend])) > 0 else "counterclockwise"


def _smooth(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


class _Rand:
    def __init__(self, seed):
        import random
        self.r = random.Random(seed)

    def __call__(self):
        return self.r.random()


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
