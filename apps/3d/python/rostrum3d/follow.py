"""Follow and Stick to surface (SPEC §8 constraints), resolved by the compiler into the item's own x y z rx ry rz
sx sy sz per frame, like an aim (resolve.py `Frames.values`).

Follow rides: frame by frame from time 0, the item takes on each step of its target's move (the target's world
transform at this frame times the inverse of its last frame's), scaled by `followAmount` there. So it never jumps:
picked up (Amount 0 → 1) it starts riding from where it stands; let go (1 → 0) it stays where it was let go, and
any part-way Amount rides that share of each step. The item's own keys still move it, inside the ride.

Follow the pose (`followPose`, on a clay or a mesh with bones): the ride is the bone's move nearest where the item sits
(its own Position at time 0, in the target's own space at rest; a mirrored copy's from its own side), the move the core
bends the surface there with (skin.py: the bone now times its rest), on top of the target's own move. It counts from
rest, not from time 0, so an item placed before posing stays on the posed surface whatever time is posed; the bone is
chosen again whenever the joints are found again. The nearest bone, by the distance the core weights the skin by
(core/src/skin.cpp, a point behind a clay bone's head counted BEHIND × farther): the heaviest bone there; on a clay
whose joints split it into pieces (skin_parts.py), only the bones of the piece the item sits on count (an eye on the
face rides the head, never the raised arm's bone beside it).

Stick stands the item's Position (its pivot) on the top of a mesh's surface straight below, `y` above it.
"""
from __future__ import annotations

from rostrum_core.keys import keys_of, track_value

from . import aim, skin, surface

TRS = ("x", "y", "z", "rx", "ry", "rz", "sx", "sy", "sz")
BEHIND = 3.0                    # core/src/clay_skin.cpp behind_head: a clay point behind a bone's head counts farther


def decompose(m) -> dict:
    """x y z rx ry rz sx sy sz of a transform (aim.local's order; any shear is dropped)."""
    lin, t = m
    s = [sum(lin[r][c] ** 2 for r in range(3)) ** 0.5 for c in range(3)]
    if s[0] * s[1] * s[2] == 0:
        return {**dict(zip(("x", "y", "z"), t)), "rx": 0.0, "ry": 0.0, "rz": 0.0, "sx": s[0], "sy": s[1], "sz": s[2]}
    if aim.det(lin) < 0:
        s[0] = -s[0]                                          # a mirror: kept on X
    rot = [[lin[r][c] / s[c] for c in range(3)] for r in range(3)]
    rx, ry, rz = aim.euler(rot)
    return {"x": t[0], "y": t[1], "z": t[2], "rx": rx, "ry": ry, "rz": rz, "sx": s[0], "sy": s[1], "sz": s[2]}


def _share(m, a: float):
    """`a` of the step m (1: all of it, 0: none)."""
    if a >= 1:
        return m
    lin, t = m
    return ([[(1 - a) * (r == c) + a * lin[r][c] for c in range(3)] for r in range(3)], [a * x for x in t])


def amount(item: dict, t: float) -> float:
    keys = keys_of(item, "followAmount")
    return min(1.0, max(0.0, float(track_value(keys, t)) if keys else float(item.get("followAmount", 1.0))))


def _target(fr, id_: str, field: str, word: str) -> str:
    target = fr.items[id_].get(field) or ""
    if target not in fr.items:
        raise ValueError(f'{id_}: {word} "{target}", which is not an item')
    if target == id_:
        raise ValueError(f"{id_}: can't {word.split()[0]} itself")
    return target


def ride(fr, id_: str, f: int):
    """The world-space move a following item has taken on by frame f (from time 0; with followPose, from rest). A
    mirrored copy rides by its original's Follow fields, on its own side (mirror.values)."""
    seq = fr.rides.get(id_)
    if seq is None or len(seq) <= f:
        if id_ in fr.riding:
            raise ValueError(f"{id_}: it follows something that moves with it (an item inside it, or one that "
                             "follows it back)")
        fr.riding.add(id_)
        try:
            source = fr.items[fr.items[id_].get("mirror") or id_]
            target = _target(fr, source["id"], "follow", "follows")
            if (carry := fr.carries.get(id_)) is None:            # its bone is found once per Frames, not per frame
                carry = fr.carries[id_] = _carry(fr, id_, source, target)
            if seq is None:
                start = (aim.compose(carry(0), aim.invert(fr.world(target, 0))) if source.get("followPose")
                         else aim.IDENTITY)
                seq = fr.rides[id_] = [_share(start, amount(source, 0.0))]
            while len(seq) <= f:
                g = len(seq)
                a = amount(source, g / fr.fps)
                step = aim.compose(carry(g), aim.invert(carry(g - 1))) if a > 0 else aim.IDENTITY
                seq.append(aim.compose(_share(step, a), seq[-1]))
        finally:
            fr.riding.discard(id_)
    return seq[max(0, f)]


def _carry(fr, id_: str, source: dict, target: str):
    """frame -> the transform the item rides on: the target's world, times the pose move of its bone nearest the item."""
    bone = nearest_bone(fr.items[target], rest_spot(fr, id_, target)) if source.get("followPose") else None
    if bone is None:
        return lambda g: fr.world(target, g)
    return lambda g: aim.compose(fr.world(target, g), bone_move(fr, target, bone, g))


def rest_spot(fr, id_: str, target: str) -> list[float]:
    """Where the item stands (its own Position, time 0) in the target's own space: a mirrored copy's from its
    original's, reflected through its clay's mirror (mirror.reflection)."""
    item = fr.items[id_]
    source = fr.items[item.get("mirror") or id_]
    p = aim.point(_parent(fr, source["id"], 0), [float(source.get(k, 0.0)) for k in ("x", "y", "z")])
    if item.get("mirror") and item.get("mirrorOn") in fr.items:
        from .mirror import reflection
        p = aim.point(reflection(fr.world(item["mirrorOn"], 0)), p)
    return aim.point(aim.invert(fr.world(target, 0)), p)


def nearest_bone(target: dict, p) -> int | None:
    """The index (skin.bones_of's order) of the bone nearest the point p (target's own space, at rest), as the core
    weighs the skin: distance to the bone, plus BEHIND × how far behind its head on a clay. None without bones or with
    Bend off."""
    chain = skin.bones_of(target)
    if not chain or not target.get("skinned", True):
        return None
    behind = BEHIND if target.get("type") == "clay" else 0.0

    def far(seg):
        a, b = seg[:3], seg[3:]
        ab = [y - x for x, y in zip(a, b)]
        ap = [y - x for x, y in zip(a, p)]
        n2 = sum(c * c for c in ab) or 1e-30
        t = sum(x * y for x, y in zip(ap, ab)) / n2
        q = [x + min(1.0, max(0.0, t)) * c for x, c in zip(a, ab)]
        return sum((x - y) ** 2 for x, y in zip(p, q)) ** 0.5 + behind * max(0.0, -t * n2 ** 0.5)

    rest = skin.transforms(chain)
    segs = [skin.segment(m, b) for m, (b, _) in zip(rest, chain)]
    if target.get("jointParts"):                # a clay's pieces: only its own piece's bones bend the surface there
        from . import skin_parts
        if parts := skin_parts.for_core(target["jointParts"], chain, segs):
            w = skin_parts.weights([p], segs, parts, reach=True)[0]
            return max(w, key=w.get)
    return min(range(len(chain)), key=lambda i: far(segs[i]))


def bone_move(fr, target: str, bone: int, g: int):
    """The bone's move at frame g in the target's own space: now times its rest (the core's skin pose)."""
    return moves(fr, target, g)[bone]


def moves(fr, target: str, g: int) -> list:
    """Every bone's move at frame g (its held frame's), in skin.bones_of's order; the clay's own skin reads them too
    (compile.py, with no animation layers: the same numbers)."""
    key = (target, fr.held(target, g))
    if key not in fr.poses:
        if (rest := fr.poses.get(target)) is None:             # its chain and the inverse of each bone's rest, once
            pose = skin.poser(skin.bones_of(fr.items[target]))
            rest = fr.poses[target] = (pose, [aim.invert(r) for r in pose(None)])
        pose, back = rest
        fr.poses[key] = [aim.compose(n, r) for n, r in zip(pose(key[1] / fr.fps), back)]
    return fr.poses[key]


def _parent(fr, id_: str, f: int):
    parent = fr.parent[id_]
    return fr.world(parent, f) if parent else aim.IDENTITY


def followed(fr, id_: str, v: dict, f: int) -> dict:
    """The item's x … sz once it rides: its own transform carried by the ride, back in its parent's space."""
    p = _parent(fr, id_, f)
    world = aim.compose(ride(fr, id_, f), aim.compose(p, aim.local(v)))
    return decompose(aim.compose(aim.invert(p), world))


def stuck(fr, id_: str, v: dict, f: int) -> dict:
    """The item's x y z standing on its stick target's surface, its y above it; unchanged off the surface's edge."""
    target = _target(fr, id_, "stick", "sticks to")
    tv = fr.values(target, f)
    if fr.items[target]["type"] != "mesh":
        raise ValueError(f'{id_}: sticks to "{target}", a {fr.items[target]["type"]}; it can stick only to a mesh')
    try:
        tris = surface.triangles(tv)
    except ValueError as e:
        raise ValueError(f'{id_}: sticks to "{target}": {e}') from None
    tw = fr.world(target, f)
    p = _parent(fr, id_, f)
    here = aim.point(p, [v["x"], 0.0, v["z"]])
    y = surface.top([[aim.point(tw, q) for q in tri] for tri in tris], here[0], here[2])
    if y is None:
        return {}
    there = aim.point(aim.invert(p), [here[0], y + v["y"], here[2]])
    return dict(zip(("x", "y", "z"), there))
