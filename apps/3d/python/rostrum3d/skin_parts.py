"""A posed clay's parts (CL7): the core bends each piece of clay with its own piece's bones, so raising an arm moves
the arm and the shoulder round it, never the body's side or hip beside the arm (the flap the five-minute wave pulled).

The joint finder (pose_joints.find_parts) knows which piece each cell of the clay belongs to: the body, or a limb
(the cells the walk inside the clay reaches only through that limb). It is kept on the clay as `jointParts` (packed
text) and sent to the core inside the clay's `skin` as `parts` (ENGINE_CONTRACT.md § Clay with bones, Parts):

    "parts": {"origin": [x y z] (the grid's low corner, clay space), "cell": metres, "dims": [nx ny nz],
              "cells": [value, count, value, count, …] (the cells x fastest, run-length: value = the piece, 255 outside),
              "bone": [piece per bone, in the skin's bone order],
              "pieces": [{"from": bone index the piece hangs from (−1 for the body), "first": its first bone,
                          "blend": metres}, …]}

The rule (the core's skin.cpp does the same; `weights` here is its reference, for tests and follow.py):
- a point's share of each piece (CL7b): each limb's cells spread through the clay's inside (never across air) within
  its reach of its joint (its first bone's head; root_reach: the whole patch where its root meets the body), each step
  an inside cell there that is not the limb's own taking the mean of itself and its 6 inside neighbours (3d-28: the
  limb's own cells keep all their share, so the spread goes out into the body only; spreading the body back into a
  thin arm left the upper arm a third the body's, and a raised arm came apart from the shoulder), round(3.5 σ²) steps (at most SHARE_MOST)
  with σ = SHARE_WIDTH × the blend in cells; cells beyond the reach keep their own piece. KEEP rings of outside cells
  round the clay take the mean of their 26 neighbours valued before them. Read trilinearly between the 8 cell centres
  round the point (cells with no value left out; none: the plain rule); beyond its reach a limb's share s is
  sharpened to smoothstep((s − 0.25) × 2), turning smoothly to s over the reach's last third (so a body point beside a
  resting limb's cell stays the body's, without cell-shaped marks); the body's share is what the limbs leave;
- per piece, each bone counts 1 / distance⁴ to its rest segment (a point behind a limb bone's head farther by BEHIND ×
  how far behind; not the body's own bones, or the low belly leans on the chest) times its gate: 1 for that piece's bones; for the body bone a limb hangs from, seen
  from the limb, 1 within the joint's `blend` of the joint and fading to 0 at twice it; 0 for every other bone (3d-28:
  a limb's first bone seen from the body was gated in too; it is so much nearer than the body's middle bones that the
  body round the joint, 2 × blend wide, turned rigidly with the arm and left a dented rim; the shares bring the limb
  into the body smoothly instead). The piece's weights: its 4 largest so,
  normalised, × the largest neighbour gate g, plus (1 − g) × the 4 largest of its own bones alone, normalised (so a
  nearer neighbour bone's share falls evenly over the blend, not all at its far end);
- the pieces' weights mixed by the point's shares; the 4 largest, normalised; an influence under PRUNE dropped and the
  rest renormalised.
So the bend is shared smoothly round each joint, the weights change smoothly across a border between pieces (CL7's
hard switch there tore the chest open under a raised arm), and the shoulder stays joined (it stretches).
"""
from __future__ import annotations

import numpy as np

from . import pose_joints as PJ

BEHIND, PRUNE, MOST = 3.0, 0.02, 4
SHARE_WIDTH, KEEP, SHARE_MOST, REACH = 1.5, 2, 256, 3.0         # skin.cpp kShareWidth, kShareRings, kShareMost, kShareReach
_LAST: list = [None, None]                                        # the last parts and their shares


def for_core(packed: str, chain: list[tuple[dict, int]], rest: list[list[float]]) -> dict | None:
    """The core's `parts` for a clay whose bones are `chain` (skin.bones_of) with rest segments `rest`, from its
    `jointParts`; None when no bone is named in it (the parts are of other joints)."""
    parts = PJ.unpack_parts(packed)
    name = [b.get("joint") or b["id"] for b, _ in chain]
    piece_of = {j: n for n, g in enumerate(parts["groups"], 1) for j in g["joints"]}
    bone = []
    for (b, p), nm in zip(chain, name):                           # a bone not in a piece is in its parent's
        bone.append(piece_of[nm] if nm in piece_of else (bone[p] if p >= 0 else 0))
    if not any(nm in piece_of for nm in name) and parts["groups"]:
        return None
    pieces = [{"from": -1, "first": 0, "blend": 0.0}]
    for n, g in enumerate(parts["groups"], 1):
        first = next((i for i, x in enumerate(bone) if x == n), -1)
        pieces.append({"from": chain[first][1] if first >= 0 else -1, "first": first, "blend": float(g["blend"])})
    lut = np.arange(256, dtype=np.uint8)                         # a piece with no bone left is the body's
    for n, pc in enumerate(pieces):
        if pc["first"] < 0:
            lut[n] = 0
    flat = lut[np.ascontiguousarray(parts["cells"].transpose(2, 1, 0)).ravel()]
    cuts = np.r_[0, np.nonzero(np.diff(flat))[0] + 1, flat.size]
    runs = np.stack([flat[cuts[:-1]].astype(np.int64), np.diff(cuts)], 1).ravel().tolist()
    return {"origin": parts["origin"], "cell": parts["cell"], "dims": parts["dims"], "cells": runs, "bone": bone,
            "pieces": pieces}


def _cells(parts: dict) -> np.ndarray:
    nx, ny, nz = parts["dims"]
    runs = np.array(parts["cells"], dtype=np.int64).reshape(-1, 2)
    return np.repeat(runs[:, 0], runs[:, 1]).astype(np.uint8).reshape(nz, ny, nx).transpose(2, 1, 0)


def piece_at(parts: dict, cells: np.ndarray, p) -> int:
    """The piece a point is in: its cell's, else the nearest inside cell's of the 26 round it; −1: none."""
    c = (np.asarray(p, float) - parts["origin"]) / parts["cell"] - 0.5      # in cell-centre units
    i = np.floor(c + 0.5).astype(int)
    best, dbest = -1, 1e9
    for o in [(0, 0, 0)] + PJ._OFFSETS:
        j = i + o
        if (j < 0).any() or (j >= cells.shape).any() or cells[tuple(j)] == 255:
            continue
        d = float(((j - c) ** 2).sum())
        if o == (0, 0, 0):
            return int(cells[tuple(j)])
        if d < dbest:
            best, dbest = int(cells[tuple(j)]), d
    return best


def _fade(x: float) -> float:
    if x <= 1:
        return 1.0
    if x >= 2:
        return 0.0
    t = 2 - x
    return t * t * (3 - 2 * t)


def piece_near(parts: dict, cells: np.ndarray, p) -> int:
    """piece_at, else the piece of the nearest inside cell anywhere: a point off the clay (an eye on its face, a part
    placed on it) belongs to the piece of the clay it sits on; −1 only for a grid with no inside cell."""
    piece = piece_at(parts, cells, p)
    if piece >= 0:
        return piece
    inside = np.argwhere(cells != 255)
    if not len(inside):
        return -1
    c = (np.asarray(p, float) - parts["origin"]) / parts["cell"] - 0.5
    j = inside[int(((inside - c) ** 2).sum(1).argmin())]
    return int(cells[tuple(j)])


def root_reach(parts: dict, cells: np.ndarray, n: int, joint) -> float:
    """How far round limb n's joint its share spreads (metres): REACH × its blend, or farther, to cover the whole of
    the patch where its root meets the clay round it (its cells beside another piece's, 26-connected, the patch with
    the cell nearest the joint) and a blend beyond; other patches (a forearm resting on the hip) stay sharp."""
    pc = parts["pieces"][n]
    inside = cells != 255
    p = np.pad(cells, 1, constant_values=255)
    other = np.zeros(cells.shape, bool)
    for a in range(3):
        for d in (-1, 1):
            q = p[tuple(slice(1 + d * (a == k), p.shape[k] - 1 + d * (a == k)) for k in range(3))]
            other |= (q != 255) & (q != n)
    face = np.argwhere((cells == n) & inside & other)
    reach = REACH * pc["blend"]
    if not len(face):
        return reach
    centre = np.asarray(parts["origin"]) + (face + 0.5) * parts["cell"]
    dist = np.linalg.norm(centre - np.asarray(joint), axis=1)
    index = {tuple(c): i for i, c in enumerate(face)}
    seen, todo = {int(dist.argmin())}, [int(dist.argmin())]
    while todo:                                                   # the root's patch
        c = face[todo.pop()]
        for o in PJ._OFFSETS:
            j = index.get((c[0] + o[0], c[1] + o[1], c[2] + o[2]))
            if j is not None and j not in seen:
                seen.add(j)
                todo.append(j)
    return max(reach, float(dist[list(seen)].max()) + pc["blend"])


def shares(parts: dict, cells: np.ndarray, rest: list[list[float]]) -> tuple[np.ndarray, list[float]]:
    """Each cell's share of each limb, float32 [limb − 1, x, y, z] (the rule above; NaN: no clay near the cell), and
    each piece's reach (root_reach; 0: none)."""
    inside = cells != 255
    valued = inside.astype(np.uint8)
    rings = []
    for r in range(KEEP):                                         # outside cells next to a valued one
        v = np.pad(valued > 0, 1)
        near = np.zeros_like(inside)
        for o in [(0, 0, 0)] + PJ._OFFSETS:
            near |= v[1 + o[0]:v.shape[0] - 1 + o[0], 1 + o[1]:v.shape[1] - 1 + o[1], 1 + o[2]:v.shape[2] - 1 + o[2]]
        ring = near & (valued == 0)
        valued[ring] = 2 + r
        rings.append(ring)
    pad_in = np.pad(inside, 1)
    count = 1 + sum(pad_in[tuple(slice(1 + d * (a == k), pad_in.shape[k] - 1 + d * (a == k)) for k in range(3))]
                    for a in range(3) for d in (-1, 1)).astype(np.float64)
    out = np.full((len(parts["pieces"]) - 1, *cells.shape), np.nan, dtype=np.float32)
    reaches = [0.0] * len(parts["pieces"])
    for n in range(1, len(parts["pieces"])):
        f = ((cells == n) & inside).astype(np.float32)
        pc = parts["pieces"][n]
        if 0 <= pc["first"] < len(rest) and pc["blend"] > 0:
            sigma = max(SHARE_WIDTH * pc["blend"] / parts["cell"], 0.5)
            centre = np.asarray(parts["origin"]) + (np.indices(cells.shape).transpose(1, 2, 3, 0) + 0.5) * parts["cell"]
            reaches[n] = root_reach(parts, cells, n, rest[pc["first"]][:3])
            free = inside & (cells != n) & (((centre - rest[pc["first"]][:3]) ** 2).sum(-1) <= reaches[n] ** 2)
            for _ in range(min(SHARE_MOST, int(np.floor(3.5 * sigma * sigma + 0.5)))):
                p = np.pad(f, 1)
                s = f.astype(np.float64)
                for a in range(3):
                    for d in (-1, 1):
                        s = s + p[tuple(slice(1 + d * (a == k), p.shape[k] - 1 + d * (a == k)) for k in range(3))]
                f = np.where(free, s / count, f).astype(np.float32)     # (outside cells hold 0, so they add nothing)
        g = np.where(inside, f, np.nan).astype(np.float32)
        for r, ring in enumerate(rings):                          # the mean of the neighbours valued before the ring
            before = np.pad((valued > 0) & (valued < 2 + r), 1)
            vals = np.pad(np.where((valued > 0) & (valued < 2 + r), np.nan_to_num(g), 0), 1)
            s, c = np.zeros(cells.shape), np.zeros(cells.shape)
            for o in [(0, 0, 0)] + PJ._OFFSETS:
                sl = tuple(slice(1 + o[k], cells.shape[k] + 1 + o[k]) for k in range(3))
                s += vals[sl]
                c += before[sl]
            g[ring] = np.where(c[ring] > 0, s[ring] / np.maximum(c[ring], 1), 0)
        out[n - 1] = g
    return out, reaches


def shares_at(parts: dict, share: tuple, p, rest: list[list[float]]) -> np.ndarray | None:
    """A point's share of each piece (the body first), trilinear between the 8 cell centres round it, sharpened beyond
    each limb's joint's reach; None: no clay near it."""
    n = len(parts["pieces"])
    if n < 2:
        return np.ones(1)
    share, reaches = share
    dims = np.array(parts["dims"])
    c = np.clip((np.asarray(p, float) - parts["origin"]) / parts["cell"] - 0.5, 0, dims - 1)
    i0 = np.minimum(np.floor(c).astype(int), np.maximum(dims - 2, 0))
    t = np.where(dims > 1, c - i0, 0.0)
    acc, wsum = np.zeros(n), 0.0
    for corner in range(8):
        up = np.array([(corner >> a) & 1 for a in range(3)])
        q = np.minimum(i0 + up, dims - 1)
        wt = float(np.prod(np.where(up == 1, t, 1 - t)))
        v = share[:, q[0], q[1], q[2]]
        if wt <= 0 or np.isnan(v[0]):
            continue
        wsum += wt
        acc[1:] += wt * v
    if wsum < 1e-9:
        return None
    acc[1:] /= wsum
    for n_, pc in enumerate(parts["pieces"][1:], 1):             # beyond the reach: sharpened (a crease splits fast)
        reach = reaches[n_]
        k = float(np.clip((reach - np.linalg.norm(np.asarray(p) - rest[pc["first"]][:3])) * 3 / reach, 0, 1)) if reach else 0.0
        x = float(np.clip((acc[n_] - 0.25) * 2, 0, 1))
        acc[n_] = k * acc[n_] + (1 - k) * x * x * (3 - 2 * x)
    acc[0] = max(0.0, 1 - acc[1:].sum())
    return acc / acc.sum()


def weights(points, rest: list[list[float]], parts: dict | None, reach: bool = False) -> list[dict[int, float]]:
    """Each point's bones and weights {bone: weight} by the rule above (parts None: the plain rule). `reach`: a point
    off the clay takes its nearest inside cell's piece (piece_near) instead of the plain rule (follow.py)."""
    cells = _cells(parts) if parts else None
    share = None
    if parts:                                                     # spread once per parts (follow.py asks point by point)
        if _LAST[0] != (parts, rest):
            _LAST[:] = [(parts, rest), shares(parts, cells, rest)]
        share = _LAST[1]
    out = []
    for p in np.asarray(points, float):
        sh = shares_at(parts, share, p, rest) if parts else None
        if sh is None and parts and reach and (piece := piece_near(parts, cells, p)) >= 0:
            sh = np.eye(len(parts["pieces"]))[piece]
        near = {}
        for b, seg in enumerate(rest):
            a, t = np.array(seg[:3]), np.array(seg[3:])
            ab = t - a
            ln = float(np.linalg.norm(ab))
            s = float(np.clip((p - a) @ ab / max(ln * ln, 1e-12), 0, 1))
            d = float(np.linalg.norm(p - (a + s * ab)))
            if ln > 0 and not (parts and parts["bone"][b] == 0):       # (CL7b: limbs only; the body's own bones not)
                d += BEHIND * max(0.0, -float((p - a) @ ab) / ln)
            near[b] = 1 / (d ** 4 + 1e-12)
        raw = dict(near)
        if sh is not None:                                       # each piece's own weights, mixed by the shares
            mix = dict.fromkeys(near, 0.0)
            def add(raw_, share_):
                top_ = sorted(((v, b) for b, v in raw_.items()), reverse=True)[:MOST]
                tot = sum(v for v, _ in top_)
                for v, b in top_ if tot > 0 else ():
                    mix[b] += share_ * v / tot
            for n, share_n in enumerate(sh):
                if share_n <= 0:
                    continue
                gates = {b: _gate(parts, n, b, p, rest) for b in near}      # mixed by the gate, not multiplied
                across = max([g for b, g in gates.items() if parts["bone"][b] != n], default=0.0)
                if across > 0:
                    add({b: gates[b] * v for b, v in near.items()}, share_n * across)
                if across < 1:
                    add({b: v if parts["bone"][b] == n else 0.0 for b, v in near.items()}, share_n * (1 - across))
            if sum(mix.values()) > 0:
                raw = mix
        top = sorted(raw.items(), key=lambda kv: -kv[1])[:MOST]
        total = sum(v for _, v in top)
        if total <= 0:                                           # (never: each piece holds a bone) the plain rule
            out += weights([p], rest, None)
            continue
        w = {b: v / total for b, v in top if v / total >= PRUNE}
        s = sum(w.values())
        out.append({b: v / s for b, v in w.items()})
    return out


def _gate(parts, piece, b, p, rest) -> float:
    if not parts or piece < 0:
        return 1.0
    if parts["bone"][b] == piece:
        return 1.0
    own = parts["pieces"][piece]
    if piece > 0 and b == own["from"]:                            # the body bone this limb hangs from
        return _fade(float(np.linalg.norm(np.asarray(p) - rest[own["first"]][:3])) / max(own["blend"], 1e-9))
    return 0.0          # (3d-28: not a limb's first bone seen from the body: the shares bring it in, smoothly)
