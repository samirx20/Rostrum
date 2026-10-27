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

The rule (the core's clay_skin.cpp does the same; `weights` here is its reference, for tests):
- a point's piece: the cell it is in, else the nearest inside cell of the 26 round it, else none (the plain rule);
- each bone counts 1 / distance⁴ to its rest segment (a point behind a bone's head farther by BEHIND × how far
  behind, as before), times a gate: 1 for the point's own piece's bones; for the bone where a piece meets its
  neighbour (a limb's first bone seen from the body, the body bone a limb hangs from seen from the limb), 1 within
  the joint's `blend` of the joint and fading to 0 at twice it; 0 for every other bone;
- the 4 largest, normalised; an influence under PRUNE dropped and the rest renormalised.
So the bend is shared smoothly only round each joint, and the shoulder stays joined (it stretches).
"""
from __future__ import annotations

import numpy as np

from . import pose_joints as PJ

BEHIND, PRUNE, MOST = 3.0, 0.02, 4


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


def weights(points, rest: list[list[float]], parts: dict | None, reach: bool = False) -> list[dict[int, float]]:
    """Each point's bones and weights {bone: weight} by the rule above (parts None: the plain rule). `reach`: a point
    off the clay takes its nearest inside cell's piece (piece_near) instead of the plain rule (follow.py)."""
    cells = _cells(parts) if parts else None
    out = []
    for p in np.asarray(points, float):
        piece = (piece_near if reach else piece_at)(parts, cells, p) if parts else -1
        raw = {}
        for b, seg in enumerate(rest):
            a, t = np.array(seg[:3]), np.array(seg[3:])
            ab = t - a
            ln = float(np.linalg.norm(ab))
            s = float(np.clip((p - a) @ ab / max(ln * ln, 1e-12), 0, 1))
            d = float(np.linalg.norm(p - (a + s * ab)))
            if ln > 0:
                d += BEHIND * max(0.0, -float((p - a) @ ab) / ln)
            raw[b] = _gate(parts, piece, b, p, rest) / (d ** 4 + 1e-12)
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
    mine = parts["bone"][b]
    if mine == piece:
        return 1.0
    pcs = parts["pieces"]
    own, other = pcs[piece], pcs[mine]
    if piece > 0 and b == own["from"]:                            # the body bone this limb hangs from
        joint, blend = rest[own["first"]][:3], own["blend"]
    elif mine > 0 and b == other["first"] and other["from"] >= 0 and parts["bone"][other["from"]] == piece:
        joint, blend = rest[b][:3], other["blend"]               # a limb hanging from this piece, at its joint
    else:
        return 0.0
    return _fade(float(np.linalg.norm(np.asarray(p) - joint)) / max(blend, 1e-9))
