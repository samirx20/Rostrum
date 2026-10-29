"""The joint finder (SPEC §4, CL5): a clay's joints found from its shape alone, so any clay can be posed by dragging.

Input: the core's `clay_grid` (the REST clay sampled at cell centres: `origin` is the grid's low corner, a cell's
centre is origin + (index + 0.5) × cell; `inside` one byte per cell, x fastest, then y, then z). numpy only.

How (plain words):
1. How deep inside each cell is (the exact distance to the outside). The deepest cell is the body's middle: the root.
2. How far each cell is from the root walking inside the clay; cells are cut into bands of that distance, and each
   band's connected pieces become the nodes of a tree (a piece touching the band before it hangs from it). Where a
   band breaks into several pieces the shape branches: the thickest piece carries on as the body, the thinner ones
   are limbs (a branch to a tip). Two pieces of about the same thickness (two legs at the hips) are both limbs.
3. A limb's middle line is its nodes' middles. It gets a joint where it meets the body, one where it bends most
   (or halfway when it is straight and longer than ~2.5× its thickness, so a straight arm still bends at the
   shoulder AND the elbow), and a wrist where its end thickens into a hand.
4. Names by where a limb joins and points: arm / forearm / hand, leg / shin / foot, a short limb at the bottom a
   foot, one pointing up from the top a neck / head, one pointing back a tail, else part3, part4 …; limbs on the
   clay's +X side are .L (the character's left, facing +Z), on −X .R. The body: body (the root), chest (from where
   the arms join), head (above a narrowing).

Out: joints, parents first: {"joint", "parent" (a joint name or None), "head" [x y z], "tail" [x y z]} in the clay's
own space. `merge` keeps placed joints; `rest_bones` turns joints into bone fields (ops_bones' minimal-turn
convention); `out_of_date` tells a clay whose shape changed since its joints were found.
"""
from __future__ import annotations

import base64
import math

import numpy as np

from . import aim
from .ops_bones import _arc, _t, _unit

BODY = ("body", "chest", "neck", "head")           # the body's own bones (they turn less in a drag: pose_ik)
HUMANOID = {"body": "Hips", "chest": "Spine", "neck": "Neck", "head": "Head",
            "arm.L": "LeftUpperArm", "forearm.L": "LeftLowerArm", "hand.L": "LeftHand",
            "arm.R": "RightUpperArm", "forearm.R": "RightLowerArm", "hand.R": "RightHand",
            "leg.L": "LeftUpperLeg", "shin.L": "LeftLowerLeg", "foot.L": "LeftFoot", "toe.L": "LeftToes",
            "leg.R": "RightUpperLeg", "shin.R": "RightLowerLeg", "foot.R": "RightFoot", "toe.R": "RightToes"}
CHAINS = {"arm": ("arm", "forearm", "hand"), "leg": ("leg", "shin", "foot"), "foot": ("foot", "toe"),
          "head": ("neck", "head"), "tail": ("tail",), "part": ("part",)}
SIDED = ("arm", "leg", "foot")
LONG = 2.5                     # a limb longer than this many times its thickness gets a middle joint
BEND = 25.0                    # degrees: a bend this sharp places the middle joint there
_OFFSETS = [(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1) if (i, j, k) != (0, 0, 0)]


# --- the grid
def occupancy(grid: dict) -> np.ndarray:
    """The grid's inside cells as a bool array indexed [x, y, z]; its outer layer is always outside."""
    if "occupancy" in grid:                        # tests and callers that already hold the array ([x, y, z])
        occ = np.array(grid["occupancy"], dtype=bool)
    else:
        nx, ny, nz = (int(n) for n in grid["dims"])
        raw = np.frombuffer(base64.b64decode(grid["inside"]), dtype=np.uint8)
        if raw.size != nx * ny * nz:
            raise ValueError(f"clay_grid: {raw.size} cells for dims {nx}×{ny}×{nz}")
        occ = raw.reshape(nz, ny, nx).transpose(2, 1, 0) != 0
    occ = occ.copy()
    occ[0], occ[-1], occ[:, 0], occ[:, -1], occ[:, :, 0], occ[:, :, -1] = False, False, False, False, False, False
    return occ


def depth(occ: np.ndarray) -> np.ndarray:
    """Each cell's exact distance (in cells) to the nearest outside cell centre; 0 outside (separable squared EDT)."""
    big = float(sum(occ.shape) ** 2)
    d = np.where(occ, big, 0.0).astype(np.float32)
    for axis in range(3):
        d = np.moveaxis(d, axis, -1)
        n, shape = d.shape[-1], d.shape
        lines = d.reshape(-1, n)
        sq = (np.arange(n)[:, None] - np.arange(n)[None, :]).astype(np.float32) ** 2       # (i, j)
        step = max(1, 4_000_000 // (n * n))
        out = np.empty_like(lines)
        for s in range(0, lines.shape[0], step):
            out[s:s + step] = (lines[s:s + step, None, :] + sq[None]).min(axis=2)
        d = np.moveaxis(out.reshape(shape), -1, axis)
    return np.sqrt(d)


def _shift(o) -> tuple[tuple, tuple]:
    """(to, from) slices pairing each cell with its neighbour at −o (what np.roll(a, o) puts there), no wrap-around:
    the grid's outer layer is outside, so the wrapped cells never count."""
    to = tuple(slice(d, None) if d > 0 else slice(None, d) if d < 0 else slice(None) for d in o)
    fr = tuple(slice(None, -d) if d > 0 else slice(-d, None) if d < 0 else slice(None) for d in o)
    return to, fr


def walk(occ: np.ndarray, start: tuple) -> np.ndarray:
    """How far each inside cell is from `start` walking inside the clay (26 neighbours; inf where it can't reach).
    Relaxed from the cells that just got nearer until none does: each cell's shortest float32 path sum, whatever the
    order the steps are tried in."""
    g = np.full(occ.shape, np.inf, dtype=np.float32)
    if not occ[start]:
        return g
    idx = np.flatnonzero(occ)                               # inside cells are never on the outer layer: x + o fits
    pos = np.full(occ.size, -1, dtype=np.int64)
    pos[idx] = np.arange(len(idx))
    strides = (occ.shape[1] * occ.shape[2], occ.shape[2], 1)
    nbr = pos[idx[:, None] + np.array([sum(c * s for c, s in zip(o, strides)) for o in _OFFSETS])]      # (cells, 26)
    w = np.array([math.sqrt(sum(c * c for c in o)) for o in _OFFSETS], dtype=np.float32)
    near = np.full(len(idx), np.inf, dtype=np.float32)
    front = np.array([pos[np.ravel_multi_index(tuple(int(s) for s in start), occ.shape)]])
    near[front] = 0.0
    while front.size:
        to, val = nbr[front], near[front][:, None] + w
        m = to >= 0
        to, val = to[m], val[m]
        m = val < near[to]
        if not m.any():
            break
        to, val = to[m], val[m]
        np.minimum.at(near, to, val)
        front = np.unique(to)
    g.ravel()[idx] = near
    return g


def _pieces(occ: np.ndarray, band: np.ndarray) -> np.ndarray:
    """Connected pieces of cells sharing a band (26 neighbours): each inside cell's label (the flat index of the
    piece's first cell); −1 outside."""
    idx = np.nonzero(occ.ravel())[0]
    pos = np.full(occ.size, -1, dtype=np.int64)
    pos[idx] = np.arange(len(idx))
    pos = pos.reshape(occ.shape)
    a_, b_ = [], []
    for o in _OFFSETS[13:]:                                     # each neighbour pair once
        to, fr = _shift(o)
        a, b = pos[to], pos[fr]
        m = (a >= 0) & (b >= 0) & (band[to] == band[fr])
        a_.append(a[m])
        b_.append(b[m])
    a, b = np.concatenate(a_), np.concatenate(b_)
    lab = np.arange(len(idx))                                   # union-find: a root hooks onto the smaller root
    while True:
        la, lb = lab[a], lab[b]
        diff = la != lb
        if not diff.any():
            break
        np.minimum.at(lab, np.maximum(la, lb)[diff], np.minimum(la, lb)[diff])
        while not np.array_equal(nxt := lab[lab], lab):         # pointer jumping to the roots
            lab = nxt
    out = np.full(occ.size, -1, dtype=np.int64)
    out[idx] = idx[lab]
    return out.reshape(occ.shape)


# --- the tree
class _Node:
    __slots__ = ("id", "band", "cells", "radius", "pos", "far", "parent", "kids")

    def __init__(self, id_, band, cells, radius, pos, far):
        self.id, self.band, self.cells, self.radius, self.pos, self.far = id_, band, cells, radius, pos, far
        self.parent, self.kids = None, []


def _tree(occ, dist, g, width):
    band = np.where(occ, np.floor(g / width), -1).astype(np.int64)
    lab = _pieces(occ, band)
    ids = np.unique(lab[lab >= 0])
    where = {int(v): i for i, v in enumerate(ids)}
    flat_lab, flat_d, flat_g = lab.ravel(), dist.ravel(), g.ravel()
    inside = np.nonzero(flat_lab >= 0)[0]
    order = np.argsort(flat_lab[inside], kind="stable")
    sorted_cells, sorted_lab = inside[order], flat_lab[inside][order]
    cuts = np.nonzero(np.diff(sorted_lab))[0] + 1
    coords = np.stack(np.unravel_index(sorted_cells, occ.shape), axis=1).astype(np.float64)
    nodes = []
    for i, (a, b) in enumerate(zip(np.r_[0, cuts], np.r_[cuts, len(sorted_cells)])):
        d = flat_d[sorted_cells[a:b]].astype(np.float64)
        w = d * d + 1e-9
        pos = (coords[a:b] * w[:, None]).sum(0) / w.sum()
        gs = flat_g[sorted_cells[a:b]]
        far = coords[a:b][gs >= gs.max() - 0.75].mean(0)          # the middle of its cells furthest from the root
        nodes.append(_Node(i, int(band.ravel()[sorted_cells[a]]), b - a, float(d.max()), pos, far))
    # links: a piece hangs from the piece of the band before it it touches most
    touch: dict[int, dict[int, int]] = {}
    key = occ.size + 1
    for o in _OFFSETS[13:]:                                     # each neighbour pair once (and the other way below)
        to, fr = _shift(o)
        here_lab, nb_lab, here_band, nb_band = lab[to], lab[fr], band[to], band[fr]
        for hi_lab, lo_lab, hi_band, lo_band in ((here_lab, nb_lab, here_band, nb_band),
                                                 (nb_lab, here_lab, nb_band, here_band)):
            m = (hi_lab >= 0) & (lo_lab >= 0) & (hi_band == lo_band + 1)
            if not m.any():
                continue
            codes, counts = np.unique(hi_lab[m] * key + lo_lab[m], return_counts=True)     # pairs, sorted
            for code, c in zip(codes.tolist(), counts.tolist()):
                h, l_ = divmod(code, key)
                row = touch.setdefault(where[h], {})
                row[where[l_]] = row.get(where[l_], 0) + c
    for n in nodes:
        if n.id in touch:
            n.parent = max(touch[n.id].items(), key=lambda kv: kv[1])[0]
            nodes[n.parent].kids.append(n.id)
    node_of = np.full(occ.shape, -1, dtype=np.int32)          # each inside cell's node
    node_of[lab >= 0] = np.searchsorted(ids, lab[lab >= 0])
    return nodes, node_of


def _deepest(nodes, i) -> list[int]:
    """The path from node i to the tip furthest down its subtree (by bands)."""
    best: dict[int, tuple[int, int]] = {}
    for n in sorted((nodes[j] for j in _subtree(nodes, i)), key=lambda n: -n.band):
        tip = max((best[k] for k in n.kids), default=(n.band, n.id))
        best[n.id] = tip
    path = [i]
    while nodes[path[-1]].kids:
        path.append(max(nodes[path[-1]].kids, key=lambda k: best[k]))
    return path


def _subtree(nodes, i) -> list[int]:
    out, stack = [], [i]
    while stack:
        j = stack.pop()
        out.append(j)
        stack += nodes[j].kids
    return out


def _thick(nodes, i, reach=3) -> float:
    """How thick a branch is where it starts: the biggest radius over its first few bands."""
    out, frontier = 0.0, [i]
    for _ in range(reach):
        out = max([out] + [nodes[j].radius for j in frontier])
        frontier = [k for j in frontier for k in nodes[j].kids]
    return out


# --- limbs
def _smooth(pts: np.ndarray) -> np.ndarray:
    if len(pts) < 3:
        return pts
    out = pts.copy()
    out[1:-1] = (pts[:-2] + 2 * pts[1:-1] + pts[2:]) / 4
    return out


def _arclen(pts: np.ndarray) -> np.ndarray:
    return np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]


def _dense(pts: np.ndarray, step: float = 0.5) -> np.ndarray:
    """The polyline resampled every `step` (cells), its ends kept."""
    s = _arclen(pts)
    xs = np.r_[np.arange(0.0, s[-1], step), s[-1]] if s[-1] > step else s[[0, -1]]
    return np.stack([np.interp(xs, s, pts[:, c]) for c in range(3)], axis=1)


def _thickness(radii: np.ndarray) -> float:
    """A limb's thickness (cells): twice its depth, its thicker part (not its tapering tip)."""
    return 2 * float(np.percentile(radii, 75))


def _at(pts: np.ndarray, s: np.ndarray, x: float) -> np.ndarray:
    return np.array([np.interp(x, s, pts[:, c]) for c in range(3)])


def _limb_joints(pts: np.ndarray, radii: np.ndarray, kind: str) -> list[np.ndarray]:
    """The joint points along a limb's middle line (its head first, its tip last); `radii`: how deep the clay is at
    each point (cells)."""
    s = _arclen(pts)
    length, thick = s[-1], _thickness(radii)
    if length <= LONG * thick or len(pts) < 3:
        return [pts[0], pts[-1]]
    end = length
    if kind in ("arm", "leg", "head") and len(pts) >= 5:      # an end that thickens: a hand (a wrist before it)
        late, early = (s >= 0.55 * length) & (s < length - 1e-9), s < 0.55 * length
        if late.any() and early.any():
            i = int(np.argmax(np.where(late, radii, -1.0)))
            if radii[i] > 1.25 * float(np.median(radii[early])):
                end = max(s[i] - radii[i], 0.45 * length)
    k = max(1, int(round(len(pts) * thick / max(length, 1e-9) / 2)))
    bends = np.zeros(len(pts))
    for i in range(k, len(pts) - k):
        a, b = pts[i] - pts[i - k], pts[i + k] - pts[i]
        c = np.dot(a, b) / max(np.linalg.norm(a) * np.linalg.norm(b), 1e-12)
        bends[i] = math.degrees(math.acos(max(-1.0, min(1.0, c))))
    inner = (s > 0.2 * end) & (s < 0.85 * end)
    mid = s[np.argmax(np.where(inner, bends, -1))] if inner.any() and bends[inner].max() > BEND else 0.5 * end
    stops = [mid] + ([end] if end < length else [])
    if kind == "leg" and end == length:
        late = s > 0.65 * length
        if late.any() and bends[late].max() > 35:              # the foot turned forward: an ankle
            stops.append(s[late][np.argmax(bends[late])])
    stops = sorted(x for x in stops if 0.1 * length < x < 0.95 * length)
    return [pts[0], *(_at(pts, s, x) for x in stops), pts[-1]]


def _classify(base, tip, root, radius0, mirrored: bool) -> str:
    d = tip - base
    d = d / max(np.linalg.norm(d), 1e-12)
    low = base[1] < root[1] - 0.3 * radius0 or (base[1] < root[1] and tip[1] < root[1] - 0.6 * radius0)
    down = d[1] < -0.5 or tip[1] < root[1] - 0.8 * radius0     # a leg goes down or reaches the bottom; a low arm
    if low and down:                                            # held out sideways is still an arm
        return "leg"
    if d[1] > 0.7 and not mirrored:
        return "head"
    if d[2] < -0.6 and not mirrored:
        return "tail"
    if abs(d[2]) > 0.8:                                # sticking out to the front or back, not low: a nose, a
        return "part"                                  # belly bump, a snout; never an arm
    if mirrored or abs(base[0]) > 0.15 * radius0:
        return "arm"
    return "part"


# --- how finely to look
SEEN = 2.2                     # a part must be this many cells thick (radius) for the finder to see it
CAP = 72                       # the finest grid asked for (the finder takes ~0.7 s there; ~0.1 s at 48)


def thinnest(clay: dict) -> float:
    """The radius (metres) of the smallest part the clay was built from (an added ball, capsule or outline, by how fat
    it is); 0 when it has none to measure. What the grid has to resolve: a part under ~2 cells thick is a few cells in
    the grid, and the finder takes it for a bump of the surface (the 1280×720 foot)."""
    from . import clay_shapes as G
    out = []
    for st in clay.get("steps") or []:
        if st.get("step") != "piece" or st.get("hidden") or st.get("mode", "add") != "add":
            continue
        if st.get("shape") == "outline" and len(st.get("outline") or []) >= 3:
            out.append(G.inner_radius(st["outline"]) * max(1.0, float(st.get("puff", 1.0))))
        elif st.get("shape") in ("sphere", "capsule") and st.get("radius"):
            out.append(float(st["radius"]))
    return min((r for r in out if r > 1e-6), default=0.0)


def finer_cells(clay: dict, grid: dict, asked: int) -> int:
    """The grid size to ask for after the first sample (`asked` cells along the longest side): finer when the clay's
    smallest part would be thinner than SEEN cells, else `asked`. Size-independent: the same character at any size
    gets the same cells."""
    r = thinnest(clay)
    cell = float(grid.get("cell", 0.0))
    if r <= 0 or cell <= 0:
        return asked
    if r / cell >= SEEN:
        return asked
    nx, ny, nz = (int(n) for n in grid["dims"]) if "dims" in grid else grid["occupancy"].shape
    return int(min(CAP, max(asked, math.ceil(max(nx, ny, nz) * cell * SEEN / r))))


# --- the finder
def _bumps(nodes, kids, smallest) -> list[int]:
    """The kids that are real branches: a crumb a few cells big (where a band grazes a dent) is not one."""
    return [k for k in kids if sum(nodes[j].cells for j in _subtree(nodes, k)) >= smallest]


def _carry(nodes, kids, radius0, side) -> int | None:
    """Which kid carries the body on at a branching (kids thickest first), or None: the body ends here (two legs at
    the hips). The thickest carries on when clearly thicker; else the thickest one in the middle (x ≈ 0) when the
    others are off to the sides (arms either side of the top of the head)."""
    a, b = _thick(nodes, kids[0]), _thick(nodes, kids[1])
    if a >= 1.3 * b or a >= 0.6 * radius0:
        return kids[0]
    middle = [k for k in kids if abs(side(nodes[k].pos)) < 0.3 * radius0]
    return middle[0] if middle and len(middle) < len(kids) else None


def _split(nodes, k, smallest, width) -> list[int]:
    """The limbs in branch k: one, unless it forks within its own thickness (in cells; `width` cells a band) of its start. Then the band ring
    it starts in is still the body's and holds the starts of two limbs (an arm and a leg leaving the body side by side:
    whether they share a ring depends on where the bands fall, so the same clay sampled a hair differently found both
    arms on one run and none on the next); each fork is its own limb, split the same way. Forks farther out (fingers,
    toes) stay in their limb."""
    j, kids = k, _bumps(nodes, nodes[k].kids, smallest)
    while len(kids) == 1:
        j = kids[0]
        kids = _bumps(nodes, nodes[j].kids, smallest)
    if len(kids) < 2 or (nodes[j].band - nodes[k].band) * width > _thick(nodes, k):
        return [k]
    return [s for c in kids for s in _split(nodes, c, smallest, width)]


TALL = 1.4                    # a body this many times its ball's radius above the ball's middle carries a head
BACK = 2.5                     # a limb's base is at most this many times its thickness (radius) behind its first point


def _base(pts, radius, occ, dist) -> np.ndarray:
    """Where a limb leaves the body: back from its first middle point, against its way, while the clay there is no
    deeper than the limb is thick, and never farther back than about its thickness (a limb leaving a round body at a
    slant would otherwise slide along the body's skin, where the clay stays shallow, to the neck or the back)."""
    d = pts[min(2, len(pts) - 1)] - pts[0]
    d = d / max(np.linalg.norm(d), 1e-12)
    p, hi = pts[0].copy(), np.array(occ.shape) - 1
    for _ in range(int(2 * (BACK * radius + 1))):
        q = p - 0.5 * d
        c = tuple(np.clip(np.rint(q).astype(int), 0, hi))
        if not occ[c] or dist[c] > 1.4 * radius + 0.5:
            break
        p = q
    return p


def mirrored(grid: dict, occ: np.ndarray | None = None) -> bool:
    """The clay is left-right symmetric across its own X = 0, within a cell (at most 2 % of its cells differ)."""
    occ = occupancy(grid) if occ is None else occ
    origin, cell = float(grid.get("origin", (0, 0, 0))[0]), float(grid.get("cell", 1.0))
    flip = -2 * origin / cell - 1                    # cell i's mirror is cell flip − i
    shift = int(round(flip)) - (occ.shape[0] - 1)
    if abs(flip - round(flip)) > 0.25 or abs(shift) > 1:
        return False
    other = np.zeros_like(occ)
    src = occ[::-1]
    if shift >= 0:
        other[shift:] = src[:occ.shape[0] - shift]
    else:
        other[:shift] = src[-shift:]
    return int((other != occ).sum()) <= 0.02 * max(int(occ.sum()), 1)


def _mirror(joints: list[dict]) -> list[dict]:
    """Every .L joint also as its .R twin (x mirrored), parents first."""
    out = []
    flip = lambda n: n[:-2] + ".R" if n and n.endswith(".L") else n  # noqa: E731
    for j in joints:
        out.append(j)
        if j["joint"].endswith(".L"):
            out.append({"joint": flip(j["joint"]), "parent": flip(j["parent"]),
                        "head": j["head"] * np.array([-1.0, 1, 1]), "tail": j["tail"] * np.array([-1.0, 1, 1])})
    return out


def find(grid: dict, mirror: bool | None = None) -> list[dict]:
    """find_parts' joints alone."""
    return find_parts(grid, mirror)[0]


def find_parts(grid: dict, mirror: bool | None = None) -> tuple[list[dict], dict]:
    """The joints of the clay sampled in `grid` (a clay_grid reply, or {"occupancy": bool[x, y, z], "origin", "cell"}):
    parents first, {"joint", "parent", "head", "tail"} in the clay's own space (metres). A mirrored clay (`mirror`;
    None: when the grid is left-right symmetric, `mirrored`) is read on its +X half and the joints mirrored, so .L and
    .R are always a matched pair and the middle joints sit on X = 0.
    And the clay's parts (`parts`, below): which piece (the body or a limb) each cell belongs to, so the core bends
    a limb's clay with the limb's bones and the body's with the body's (a hanging arm no longer pulls the hip)."""
    occ = occupancy(grid)
    whole = occ
    half = mirrored(grid, occ) if mirror is None else bool(mirror)
    if occ.sum() < 8:
        raise ValueError("the clay is too small or too thin to find joints in (sample it with more cells)")
    origin, cell = np.array(grid.get("origin", (0, 0, 0)), dtype=np.float64), float(grid.get("cell", 1.0))
    where = lambda p: origin + (np.asarray(p, dtype=np.float64) + 0.5) * cell  # noqa: E731     (a cell's centre)
    side = lambda p: where(p)[0] / cell  # noqa: E731     (x in cells from the clay's mirror plane)
    dist = depth(occ)                                           # depth from the whole clay, even when read on a half
    if half:                                                    # +X half and the middle column(s)
        xs_ = origin[0] + (np.arange(occ.shape[0]) + 0.5) * cell
        occ = occ & (xs_ >= -0.5 * cell - 1e-9)[:, None, None]
    root_cell = np.unravel_index(int(np.argmax(np.where(occ, dist, 0))), occ.shape)
    radius0 = float(dist[root_cell])
    g = walk(occ, root_cell)
    occ = occ & np.isfinite(g)                                  # a loose crumb the root can't reach is left out
    width = max(1.0, min(2.0, radius0 / 4))                    # cells per band
    nodes, node_of = _tree(occ, dist, g, width)
    root = next(n.id for n in nodes if n.parent is None and n.band == 0)
    smallest = max(6, int(0.003 * occ.sum()))
    # the body: from the root, at each branching one piece carries on (_carry); the others are limbs
    body, limbs, i = [root], [], root
    while kids := sorted(_bumps(nodes, nodes[i].kids, smallest), key=lambda k: -_thick(nodes, k)):
        nxt = kids[0] if len(kids) == 1 else _carry(nodes, kids, radius0, side)
        limbs += [(i, s) for k in kids if k != nxt for s in _split(nodes, k, smallest, width)]
        if nxt is None:
            break
        i = nxt
        body.append(i)
    root_pos = np.asarray(root_cell, dtype=np.float64)
    body_pts = [root_pos] + [nodes[j].pos for j in body[1:]]
    tip = nodes[body[-1]].far if len(body) > 1 else root_pos + np.array([0.0, radius0, 0.0])
    body_pts.append(tip)
    # limbs: middle lines from where they leave the body to their very tip
    found = []
    for at, k in limbs:
        path = _deepest(nodes, k)
        pts = np.array([nodes[j].pos for j in path] + [nodes[path[-1]].far])
        radii = np.array([nodes[j].radius for j in path] + [nodes[path[-1]].radius])
        base = _base(pts, float(np.median(radii)), occ, dist)
        if np.linalg.norm(base - pts[0]) > 0.5:
            pts, radii = np.vstack([base, pts]), np.r_[radii[0], radii]
        pts = _dense(_smooth(pts))
        cells = np.clip(np.rint(pts).astype(int), 0, np.array(occ.shape) - 1)
        radii = np.maximum(dist[cells[:, 0], cells[:, 1], cells[:, 2]], 0.5)    # how deep the clay is along it
        if _arclen(pts)[-1] < 0.6 * max(radii.max(), 1.0):     # shorter than it is thick: a bump, not a limb
            continue
        found.append({"pts": pts, "radii": radii, "k": k})
    xs = lambda f: side(f["pts"][0])  # noqa: E731
    for f in found:
        f["central"] = abs(xs(f)) < 0.5 * _thickness(f["radii"]) + 1
        f["mirrored"] = (half and not f["central"]) or any(
            abs(xs(f) + xs(o)) < 0.25 * radius0 + 0.15 * abs(xs(f)) and xs(f) * xs(o) < 0 for o in found if o is not f)
        f["kind"] = _classify(where(f["pts"][0]), where(f["pts"][-1]), where(root_pos), radius0 * cell, f["mirrored"])
    # the body's joints, along the way from the root to its far end: root, chest where the arms join, a head above a
    # narrowing
    u = tip - root_pos
    span = max(float(np.linalg.norm(u)), 1e-9)
    u = u / span
    along = lambda p: float(np.dot(np.asarray(p) - root_pos, u))  # noqa: E731
    marks = np.maximum.accumulate(np.array([along(p) for p in body_pts]))
    at_along = lambda x: np.array([np.interp(x, marks, [p[c] for p in body_pts]) for c in range(3)])  # noqa: E731
    stops = [("body", 0.0)]
    arms = [along(f["pts"][0]) for f in found if f["kind"] == "arm"]
    if arms and 0.15 * span < sum(arms) / len(arms) < 0.9 * span:
        stops.append(("chest", sum(arms) / len(arms)))
    radii = np.array([nodes[j].radius for j in body] + [0.0])
    after = [n for n, m in enumerate(marks) if m > stops[-1][1] + 1.0][:-1]
    if len(after) > 3:                                          # the thinnest neck with a wider head above it
        necks = [n for n in after[:-1] if radii[n] < 0.75 * radii[: n + 1].max() and radii[n + 1:].max() > 1.2 * radii[n]]
        if necks:
            stops.append(("head", float(marks[min(necks, key=lambda n: radii[n])])))
    if stops[-1][0] != "head" and span > TALL * radius0 and radius0 > stops[-1][1] + 1.0:
        stops.append(("head", radius0))                        # no neck, but something sits on the body's ball: a
                                                               # head blended in; it turns from the ball's top
    joints = []
    for n, (name, x) in enumerate(stops):
        head = root_pos if n == 0 else at_along(x)
        end = at_along(stops[n + 1][1]) if n + 1 < len(stops) else tip
        joints.append({"joint": name, "parent": joints[-1]["joint"] if joints else None, "head": where(head),
                       "tail": where(end), "from": x})

    def body_bone(p):
        x = along(p) + 0.25 * radius0
        return ([j for j in joints[:len(stops)] if j["from"] <= x] or joints[:1])[-1]["joint"]
    # limbs: names, sides, chains (sorted so names come out the same every time)
    used: dict[str, int] = {}
    parts = 2
    groups = []                                                 # per limb: its joint names, its piece's cells
    for f in sorted(found, key=lambda f: (f["kind"], -xs(f), float(f["pts"][0][1]))):
        pts = f["pts"]
        cuts = _limb_joints(pts, f["radii"], f["kind"])
        kind = "foot" if f["kind"] == "leg" and _arclen(pts)[-1] <= LONG * _thickness(f["radii"]) else f["kind"]
        names = ["head"] if kind == "head" and len(cuts) == 2 else list(CHAINS[kind])
        if kind == "part":
            parts += 1
            names = [f"part{parts}"]
        sided = (".L" if xs(f) > 0 else ".R") if kind in SIDED or (half and not f["central"]) else ""
        parent = body_bone(pts[0])
        group = {"joints": [], "cells": _subtree(nodes, f["k"]), "blend": _blend(f, dist, cell)}
        groups.append(group)
        for n in range(len(cuts) - 1):
            base = names[n] if n < len(names) else f"{names[-1]}{'_' if names[-1][-1].isdigit() else ''}{n - len(names) + 2}"
            used[base + sided] = used.get(base + sided, 0) + 1
            name = base + sided if used[base + sided] == 1 else f"{base}{used[base + sided]}{sided}"
            joints.append({"joint": name, "parent": parent, "head": where(cuts[n]), "tail": where(cuts[n + 1])})
            group["joints"].append(name)
            parent = name
    if half:
        for j in joints:                                       # the middle ones on the mirror plane
            if not j["joint"].endswith(".L"):
                j["head"], j["tail"] = j["head"] * np.array([0.0, 1, 1]), j["tail"] * np.array([0.0, 1, 1])
        joints = _mirror(joints)
    out = [{"joint": j["joint"], "parent": j["parent"], "head": [round(float(x), 6) + 0.0 for x in j["head"]],
            "tail": [round(float(x), 6) + 0.0 for x in j["tail"]]} for j in joints]
    return out, _parts(whole, node_of, groups, grid, half)


# --- parts: which piece each cell belongs to
def _blend(f, dist, cell) -> float:
    """How far round a limb's first joint its bend is shared with the body (metres): 1.5 × the limb's radius where it
    leaves the body."""
    return round(1.5 * max(0.5 * _thickness(f["radii"]), 1.0) * cell, 6)


def _parts(occ, node_of, groups, grid, half) -> dict:
    """{"origin", "cell", "dims", "cells": uint8 [x, y, z] (0 = the body, n = groups[n − 1], 255 = outside),
    "groups": [{"joints": [names], "blend": metres}]} (skin_parts.py reads it). Read on a half, the other half is the
    mirror, its groups the .R twins."""
    cells = np.where(occ, 0, 255).astype(np.uint8)
    out = []
    for n, gr in enumerate(groups, 1):
        cells[np.isin(node_of, gr["cells"]) & occ] = n
        out.append({"joints": gr["joints"], "blend": gr["blend"]})
    if half:
        flip = lambda n: n[:-2] + ".R" if n.endswith(".L") else n  # noqa: E731
        twin = {}
        for n, gr in enumerate(list(out), 1):
            if any(j.endswith(".L") for j in gr["joints"]):
                out.append({"joints": [flip(j) for j in gr["joints"]], "blend": gr["blend"]})
                twin[n] = len(out)
        origin, cell = float(grid.get("origin", (0, 0, 0))[0]), float(grid.get("cell", 1.0))
        xs = origin + (np.arange(occ.shape[0]) + 0.5) * cell
        lut = np.arange(256, dtype=np.uint8)
        for a, b in twin.items():
            lut[a] = b
        other = int(round(-2 * origin / cell - 1))              # cell i's mirror is cell other − i
        for i in np.nonzero(xs < -0.5 * cell - 1e-9)[0]:
            m = other - i
            src = cells[m] if 0 <= m < occ.shape[0] else np.full_like(cells[i], 255)
            cells[i] = np.where(occ[i], np.where(src == 255, 254, lut[src]), 255)
        _fill_strays(cells)
    return {"origin": [float(x) for x in grid.get("origin", (0, 0, 0))], "cell": float(grid.get("cell", 1.0)),
            "dims": list(occ.shape), "cells": cells, "groups": out}


def _fill_strays(cells: np.ndarray) -> None:
    """Inside cells on the mirrored half whose twin is outside (254: the clay's sampling is not exactly symmetric)
    take the piece of the inside cells beside them, the most common of their 26 (an arm's skin cell was the body's,
    and a raised arm left it behind); one with none beside it, after a few rounds, the body's."""
    for _ in range(4):
        todo = np.argwhere(cells == 254)
        if not len(todo):
            return
        p = np.pad(cells, 1, constant_values=255)
        got = []
        for c in todo:
            near = p[c[0]:c[0] + 3, c[1]:c[1] + 3, c[2]:c[2] + 3].ravel()
            near = near[near < 254]
            got.append(int(np.bincount(near).argmax()) if len(near) else 254)
        cells[tuple(todo.T)] = got
    cells[cells == 254] = 0


def pack_parts(parts: dict) -> str:
    """The parts as one compact text (the clay's `jointParts`): base64 of zlib'd JSON, the cells as base64 bytes."""
    import json
    import zlib
    raw = np.ascontiguousarray(parts["cells"].transpose(2, 1, 0)).tobytes()      # x fastest
    body = {**parts, "cells": base64.b64encode(raw).decode()}
    return base64.b64encode(zlib.compress(json.dumps(body, separators=(",", ":")).encode(), 9)).decode()


def unpack_parts(text: str) -> dict:
    """pack_parts' text back: cells as uint8 [x, y, z]."""
    import json
    import zlib
    body = json.loads(zlib.decompress(base64.b64decode(text)))
    nx, ny, nz = body["dims"]
    cells = np.frombuffer(base64.b64decode(body["cells"]), np.uint8).reshape(nz, ny, nx).transpose(2, 1, 0)
    return {**body, "cells": cells}


# --- joints and bones
def joints_of(clay: dict) -> list[dict]:
    """A clay's (or mesh's) bones as joints in its own space at rest, parents first (the inverse of rest_bones)."""
    from . import skin
    chain = skin.bones_of(clay)
    rest = skin.transforms(chain)
    out = []
    for (b, p), m in zip(chain, rest):
        seg = skin.segment(m, b)
        out.append({"joint": b.get("joint") or b["id"], "parent": (chain[p][0].get("joint") or chain[p][0]["id"])
                    if p >= 0 else None, "head": seg[:3], "tail": seg[3:], "placed": bool(b.get("placed")),
                    "id": b["id"]})
    return out


def merge(found: list[dict], old: list[dict]) -> list[dict]:
    """The new joints, with every placed old joint kept where it was put (same name): a chain bone ending at it ends
    there too. A placed joint the new shape no longer has stays, under its old parent if that is still found."""
    out = [dict(j, placed=False) for j in found]
    by = {j["joint"]: j for j in out}
    for o in old:
        if not o.get("placed"):
            continue
        j = by.get(o["joint"])
        if j is None:
            parent = o["parent"] if o["parent"] in by else (out[0]["joint"] if out else None)
            j = dict(o, parent=parent, placed=True)
            out.append(j)
            by[j["joint"]] = j
            continue
        for p in out:                                  # the bone before it in a chain ends at its head
            if p["joint"] == j["parent"] and _same(p["tail"], j["head"]):
                p["tail"] = list(o["head"])
        j["head"], j["placed"] = list(o["head"]), True
    return out


def _same(a, b, tol=1e-5) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def rest_bones(joints: list[dict]) -> list[dict]:
    """Each joint as bone fields in its parent's space (x y z rx ry rz length): its +Y runs from head to tail, turned
    from its parent by the smallest turn that does it (no twist; ops_bones.rest_chain's convention)."""
    world: dict[str, tuple] = {}
    out = []
    for j in joints:
        parent = world.get(j["parent"]) if j["parent"] else None
        pl, pt = parent if parent else aim.IDENTITY
        d = [b - a for a, b in zip(j["head"], j["tail"])]
        length = math.sqrt(sum(x * x for x in d))
        if length < 1e-6:
            d, length = [pl[0][1], pl[1][1], pl[2][1]], 1e-3
        new = aim._mul(_arc(_unit([pl[r][1] for r in range(3)]), _unit(d)), pl)
        rx, ry, rz = aim.euler(aim._mul(_t(pl), new))
        head = aim.point(aim.invert((pl, pt)), j["head"])
        world[j["joint"]] = (new, list(j["head"]))
        out.append({"x": head[0], "y": head[1], "z": head[2], "rx": rx, "ry": ry, "rz": rz, "length": length})
    return [{k: round(v, 6) + 0.0 for k, v in b.items()} for b in out]


def bone_id(clay_id: str, joint: str) -> str:
    """A bone's id from its clay and part name, so keys survive finding the joints again (prim-safe)."""
    return f"{clay_id}_{''.join(c if c.isalnum() else '_' for c in joint)}"


def shown_name(joint: str, names: str = "plain") -> str:
    """A joint's name as the screen shows it: the part name, or the Humanoid (Unity / VRM) name when it has one."""
    return HUMANOID.get(joint, joint) if names == "humanoid" else joint


def steps_key(clay: dict, data: dict | None = None) -> str:
    """The clay's last step key (clay_scene.chain): what its shape is now."""
    from . import clay_scene
    chain = clay_scene.chain(clay.get("steps", []), data, clay)
    return chain[-1]["key"] if chain else ""


def out_of_date(clay: dict, data: dict | None = None) -> bool:
    """No joints yet, or the shape changed since they were found (the clay's jointsKey is not its last step key)."""
    return not clay.get("bones") or clay.get("jointsKey", "") != steps_key(clay, data)
