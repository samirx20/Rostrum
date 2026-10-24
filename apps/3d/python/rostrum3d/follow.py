"""Follow and Stick to surface (SPEC §8 constraints), resolved by the compiler into the item's own x y z rx ry rz
sx sy sz per frame, like an aim (resolve.py `Frames.values`).

Follow rides: frame by frame from time 0, the item takes on each step of its target's move (the target's world
transform at this frame times the inverse of its last frame's), scaled by `followAmount` there. So it never jumps:
picked up (Amount 0 → 1) it starts riding from where it stands; let go (1 → 0) it stays where it was let go, and
any part-way Amount rides that share of each step. The item's own keys still move it, inside the ride.

Stick stands the item's Position (its pivot) on the top of a mesh's surface straight below, `y` above it.
"""
from __future__ import annotations

from rostrum_core.keys import keys_of, track_value

from . import aim, surface

TRS = ("x", "y", "z", "rx", "ry", "rz", "sx", "sy", "sz")


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
    """The world-space move a following item has taken on by frame f (from time 0)."""
    seq = fr.rides.setdefault(id_, [aim.IDENTITY])
    if len(seq) <= f:
        if id_ in fr.riding:
            raise ValueError(f"{id_}: it follows something that moves with it (an item inside it, or one that "
                             "follows it back)")
        fr.riding.add(id_)
        try:
            item, target = fr.items[id_], _target(fr, id_, "follow", "follows")
            while len(seq) <= f:
                g = len(seq)
                a = amount(item, g / fr.fps)
                step = aim.compose(fr.world(target, g), aim.invert(fr.world(target, g - 1))) if a > 0 else aim.IDENTITY
                seq.append(aim.compose(_share(step, a), seq[-1]))
        finally:
            fr.riding.discard(id_)
    return seq[max(0, f)]


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
