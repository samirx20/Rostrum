"""Pose by dragging (SPEC §4, CL5): the drag solve, fast enough for every pointer move (no document step), and the
helpers the Pose tool and `pose.drag` share. Plain Python, no Qt.

Spaces: everything is in the clay's (or mesh's) own space, as skin.py keeps its bones. Turns are a bone's absolute
Turn (rx ry rz degrees, what its keys hold); a bone with no keys is at its rest turn.

The solve is damped CCD: from the grabbed bone back towards the body, each bone turns by part of the smallest turn
that brings the grabbed spot towards the target (limbs half of it per pass, the body's own bones ~0.3 as much), pass
after pass until the spot is there or stops getting closer. A held bone, and every bone that would carry a held one
(its parents), never turns; with no holds the root never turns. So holds choose where the body bends.
"""
from __future__ import annotations

import math

from rostrum_core.keys import keys_of, track_value

from . import aim, skin
from .pose_joints import BODY

TURN = ("rx", "ry", "rz")
LIMB, TRUNK = 0.5, 0.15                 # share of the wanted turn per pass: limbs, the body's own bones (~0.3×)
SPREAD = 6                              # damped passes before the finishing ones
STEP_CAP = math.radians(40)             # never more than this per bone per pass (no flips on a far target)


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _turn(axis, angle):
    """Rotation matrix about a unit axis (Rodrigues)."""
    x, y, z = axis
    c, s = math.cos(angle), math.sin(angle)
    k = 1 - c
    return [[c + x * x * k, x * y * k - z * s, x * z * k + y * s],
            [y * x * k + z * s, c + y * y * k, y * z * k - x * s],
            [z * x * k - y * s, z * y * k + x * s, c + z * z * k]]


def _mm(a, b):
    """3×3 times 3×3, written out (aim._mul's job, ~5× faster: the solve does hundreds per move)."""
    (a0, a1, a2), (a3, a4, a5), (a6, a7, a8) = a
    (b0, b1, b2), (b3, b4, b5), (b6, b7, b8) = b
    return [[a0 * b0 + a1 * b3 + a2 * b6, a0 * b1 + a1 * b4 + a2 * b7, a0 * b2 + a1 * b5 + a2 * b8],
            [a3 * b0 + a4 * b3 + a5 * b6, a3 * b1 + a4 * b4 + a5 * b7, a3 * b2 + a4 * b5 + a5 * b8],
            [a6 * b0 + a7 * b3 + a8 * b6, a6 * b1 + a7 * b4 + a8 * b7, a6 * b2 + a7 * b5 + a8 * b8]]


def _mv(m, v):
    return [m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2], m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2]]


def _compose(parent, child):
    (pl, pt), (cl, ct) = parent, child
    q = _mv(pl, ct)
    return _mm(pl, cl), [q[0] + pt[0], q[1] + pt[1], q[2] + pt[2]]


def _at(m, p):
    q = _mv(m[0], p)
    return [q[0] + m[1][0], q[1] + m[1][1], q[2] + m[1][2]]


def _t(m):
    return [[m[0][0], m[1][0], m[2][0]], [m[0][1], m[1][1], m[2][1]], [m[0][2], m[1][2], m[2][2]]]


def _rot(rx, ry, rz):
    """aim.local's turn (X, then Y, then Z; degrees) written out: this runs many times per pointer move."""
    a, b, c = math.radians(rx), math.radians(ry), math.radians(rz)
    ca, sa, cb, sb, cc, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    return [[cc * cb, cc * sb * sa - sc * ca, cc * sb * ca + sc * sa],
            [sc * cb, sc * sb * sa + cc * ca, sc * sb * ca - cc * sa],
            [-sb, cb * sa, cb * ca]]


def _near(e, prev):
    """Euler angles e moved by whole turns to sit nearest prev (keys then ease the short way)."""
    return tuple(v + 360.0 * round((p - v) / 360.0) for v, p in zip(e, prev))


def _seg_dist(p, a, b) -> float:
    ab, ap = _sub(b, a), _sub(p, a)
    t = max(0.0, min(1.0, _dot(ap, ab) / max(_dot(ab, ab), 1e-18)))
    d = [ap[i] - t * ab[i] for i in range(3)]
    return math.sqrt(_dot(d, d))


class Rig:
    """A clay's bones as numbers for posing: rest heads and turns, the turns now (at time t), parents first (the same
    order as skin.bones_of, so chain_pose lines up with the core's skin)."""

    def __init__(self, item: dict, t: float = 0.0):
        chain = skin.bones_of(item)
        self.item, self.t = item, t
        self.bones = [b for b, _ in chain]
        self.parent = [p for _, p in chain]
        self.ids = [b["id"] for b in self.bones]
        self.index = {b["id"]: n for n, b in enumerate(self.bones)}
        self.joint = [b.get("joint") or "" for b in self.bones]
        self.length = [float(b.get("length", 0.0)) for b in self.bones]
        self.head = [[float(b.get(k, 0.0)) for k in skin.HEAD] for b in self.bones]
        self.rest_turn = [tuple(float(b.get(k, 0.0)) for k in TURN) for b in self.bones]
        self.turn = [tuple(float(track_value(keys_of(b, k), t)) if keys_of(b, k) else r for k, r in zip(TURN, rt))
                     for b, rt in zip(self.bones, self.rest_turn)]
        self.trunk = [j in BODY for j in self.joint]
        self.rest = skin.transforms(chain)

    # --- names
    def find(self, name: str) -> int:
        """A bone by id, joint name (hand.R) or Humanoid name (RightHand); ValueError naming the choices."""
        from .pose_joints import HUMANOID
        if name in self.index:
            return self.index[name]
        for n, (j, b) in enumerate(zip(self.joint, self.bones)):
            if name in (j, b.get("name"), HUMANOID.get(j)):
                return n
        raise ValueError(f'no joint "{name}"; there are: {", ".join(j or i for j, i in zip(self.joint, self.ids))}')

    # --- where things are
    def frames(self, turns: list | None = None) -> list:
        """Each bone's transform in the clay's space with these turns (default: the turns now)."""
        out = []
        for n, (h, tr) in enumerate(zip(self.head, turns or self.turn)):
            own = (_rot(*tr), h)
            out.append(_compose(out[self.parent[n]], own) if self.parent[n] >= 0 else own)
        return out

    def bone_at(self, point, turns: list | None = None, rest: bool = False) -> int:
        """The bone a spot belongs to: the nearest bone segment (posed with `turns`, or at rest); −1 with no bones."""
        frames = self.rest if rest else self.frames(turns)
        best, out = math.inf, -1
        for n, m in enumerate(frames):
            seg = skin.segment(m, self.bones[n])
            d = _seg_dist(point, seg[:3], seg[3:])
            if d < best:
                best, out = d, n
        return out

    def held(self, holds) -> set[int]:
        """Bone indices from hold names / ids, or from rest spots ([x, y, z]: the bone under it at rest)."""
        out = set()
        for h in holds or ():
            out.add(self.bone_at(h, rest=True) if isinstance(h, (list, tuple)) else self.find(h))
        out.discard(-1)
        return out

    def frozen(self, held: set[int]) -> set[int]:
        """Bones that may not turn: held ones and every bone carrying one (its parents)."""
        out = set()
        for n in held:
            while n >= 0 and n not in out:
                out.add(n)
                n = self.parent[n]
        return out

    def pose(self, turns: dict | None = None) -> list[list[float]]:
        """The core's per-bone moves (skin.py's 12 numbers: now × rest⁻¹), with `turns` ({id: (rx, ry, rz) or
        {"rx", "ry", "rz"}}) over the turns now."""
        tr = list(self.turn)
        for id_, v in (turns or {}).items():
            tr[self.index[id_]] = _as_turn(v)
        return [skin._deform(n, r) for n, r in zip(self.frames(tr), self.rest)]


def _as_turn(v) -> tuple:
    return tuple(float(v[k]) for k in TURN) if isinstance(v, dict) else tuple(float(x) for x in v)


def rig(item: dict, t: float = 0.0) -> Rig:
    """A fresh Rig (well under a millisecond for ~15 bones, so never cached: the document changes under it)."""
    return Rig(item, t)


def solve_rig(r: Rig, grab: int, local, to, held: set[int] = frozenset(), iterations: int = 60,
              tolerance: float = 5e-4) -> dict:
    """The drag solve on a rig: the turns that bring `local` (a spot in bone `grab`'s own frame, as posed now) to
    `to` (clay space). {"turns": {id: {"rx", "ry", "rz"}} for every bone that turned, "moved": [ids], "miss":
    metres from the target, "point": where the spot ended}."""
    frozen = r.frozen(held)
    chain, n = [], grab
    while n >= 0:
        chain.append(n)
        n = r.parent[n]
    movable = [b for b in chain if b not in frozen and (held or r.parent[b] >= 0)]
    frames = r.frames()
    rot = {n: [row[:] for row in frames[n][0]] for n in chain}             # world turns of the chain's bones
    local_rot = {n: _rot(*r.turn[n]) for n in chain}
    eff = _at(frames[grab], local)
    best, stalled = math.sqrt(_dot(_sub(eff, to), _sub(eff, to))), 0
    # the limbs first; the body's own bones join only when the limbs alone stop getting closer (out of their reach), so
    # a reachable drag never leans the body
    trunk_on = not any(not r.trunk[b] for b in movable)
    for n_pass in range(iterations if movable else 0):
        share = LIMB if n_pass < SPREAD else 1.0                # damped first (the bend spreads), then CCD finishes
        if best <= tolerance:
            break
        for b in movable:
            if r.trunk[b] and not trunk_on:
                continue
            head = frames[b][1]
            a, c = _sub(eff, head), _sub(to, head)
            la, lc = math.sqrt(_dot(a, a)), math.sqrt(_dot(c, c))
            if la < 1e-9 or lc < 1e-9:
                continue
            axis = _cross(a, c)
            s = math.sqrt(_dot(axis, axis))
            angle = math.atan2(s, _dot(a, c))
            if s < 1e-12 or angle < 1e-7:
                continue
            q = _turn([x / s for x in axis], min(angle * share * (TRUNK / LIMB if r.trunk[b] else 1.0), STEP_CAP))
            rot[b] = _mm(q, rot[b])
            p = r.parent[b]
            local_rot[b] = _mm(_t(rot[p]), rot[b]) if p >= 0 else rot[b]
            eff = [head[i] + v for i, v in enumerate(_mv(q, _sub(eff, head)))]
        # the chain again from its top, so the next pass turns about where the joints are now
        for b in reversed(chain):
            p = r.parent[b]
            pf = frames[p] if p >= 0 else aim.IDENTITY
            frames[b] = _compose(pf, (local_rot[b], r.head[b]))
            rot[b] = frames[b][0]
        eff = _at(frames[grab], local)
        miss = math.sqrt(_dot(_sub(eff, to), _sub(eff, to)))
        stalled = stalled + 1 if miss > best * 0.995 else 0      # out of reach: it stops getting closer
        best = min(best, miss)
        if stalled >= 3 and not trunk_on:
            trunk_on, stalled = True, 0
        elif stalled >= 3:
            break
    turns, moved = {}, []
    for b in movable:
        e = _near(aim.euler(local_rot[b]), r.turn[b])
        if max(abs(x - y) for x, y in zip(e, r.turn[b])) > 1e-4:
            turns[r.ids[b]] = dict(zip(TURN, (round(x, 6) + 0.0 for x in e)))
            moved.append(r.ids[b])
    return {"turns": turns, "moved": moved, "miss": round(best, 6), "point": [round(x, 6) for x in eff]}


# --- what the Pose tool calls (pose_link.py)
def solve(clay: dict, bone: str, local, to, holds=(), t: float = 0.0) -> dict:
    """One pointer move: the turns that bring the spot `local` (clay space, on bone `bone` as drawn at t) to `to`
    (clay space), holding `holds` (bone ids / joint names, or rest spots [x, y, z]). Solves from the clay as given
    (the press-time clay), so each move starts from the same pose. Returns solve_rig's dict."""
    r = rig(clay, t)
    g = r.find(bone)
    spot = aim.point(aim.invert(r.frames()[g]), list(local))
    return solve_rig(r, g, spot, list(to), r.held(holds))


def bone_at(clay: dict, local, t: float = 0.0) -> str | None:
    """Which bone a spot on the clay (clay space, as drawn at t) belongs to: the nearest posed segment."""
    r = rig(clay, t)
    n = r.bone_at(list(local))
    return r.ids[n] if n >= 0 else None


def chain_pose(clay: dict, turns: dict | None = None, t: float = 0.0) -> list[list[float]]:
    """The `clay_pose` payload for a drag in progress: one 12-number move per bone (skin order), `turns` over the
    clay's turns at t."""
    return rig(clay, t).pose(turns)


def held_bones(clay: dict) -> list[str]:
    """The ids of the bones under the clay's holds (its `holds`: rest spots in its own space)."""
    r = rig(clay, 0.0)
    return [r.ids[n] for n in sorted(r.held(clay.get("holds") or []))]
