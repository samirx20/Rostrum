"""Garments from sewing patterns (PR7): a mesh whose Shape is "pattern" holds flat pieces and the seams between them
(its `pieces` and `seams`, JSON text, mesh_fields.py), never the mesh. This module checks a pattern, makes its cloth
mesh (each piece cut into fine even triangles, garment_mesh.py, then bent and placed in the item's space) and the point
pairs each seam pulls together (the simulation sends them: sim/inputs.py). Made once per pattern (cached by its text).

A piece: {"name", "outline": [[x, y], …] metres in its own flat frame, "at": [x, y, z], "turn": degrees about up,
"wrap": metres}. Flat (u, v) → (r sin(u/r), v, r cos(u/r) − r) around a vertical cylinder of radius r = wrap behind
it (wrap 0: (u, v, 0)), then turned about +y by `turn` (0 faces +z, 180 faces −z), then moved by `at`.
A seam: {"a": [piece, edge], "b": [piece, edge], "flip"?}; edge i runs from outline point i to i + 1 as written.
"""
from __future__ import annotations

import functools
import json
import math

from . import garment_mesh as GM

POINTS = 9000                    # about this many points over the whole garment
SPACING = (0.005, 0.03)          # metres: the triangle size is kept within this
PIECE_KEYS = {"name", "outline", "at", "turn", "wrap"}
SEAM_KEYS = {"a", "b", "flip"}


class PatternError(ValueError):
    """A pattern that can't be made, in words naming the piece or seam and what is accepted."""


def read(text: str, what: str) -> list:
    if not text:
        return []
    try:
        out = json.loads(text) if isinstance(text, str) else text
    except json.JSONDecodeError as e:
        raise PatternError(f"{what}: not JSON text ({e.msg}); write a list, e.g. [] ") from e
    if not isinstance(out, list):
        raise PatternError(f"{what}: must be a list, not {type(out).__name__}")
    return out


def text(value: list) -> str:
    """Pieces or seams as the document stores them: compact JSON text."""
    return json.dumps(value, separators=(",", ":"))


def _crosses(p, q, r, s) -> bool:
    o = lambda a, b, c: (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])  # noqa: E731
    return o(p, q, r) * o(p, q, s) < 0 and o(r, s, p) * o(r, s, q) < 0


def _num(v, where: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
        raise PatternError(f"{where}: {v!r} is not a number")
    return float(v)


def check(pieces: list, seams: list) -> None:
    """Raises PatternError naming the first problem: a piece without a unique name or with fewer than 3 points, an outline
    crossing itself, a seam naming a missing piece or edge, or an edge sewn twice."""
    names = {}
    for n, pc in enumerate(pieces):
        if not isinstance(pc, dict) or not isinstance(pc.get("name"), str) or not pc["name"]:
            raise PatternError(f'piece {n}: needs a "name" (text); a piece is {{"name", "outline", "at", "turn", "wrap"}}')
        name, extra = pc["name"], set(pc) - PIECE_KEYS
        if extra:
            raise PatternError(f'piece "{name}": has {", ".join(sorted(extra))}; a piece has {", ".join(sorted(PIECE_KEYS))}')
        if name in names:
            raise PatternError(f'piece "{name}": the name is used twice; each piece needs its own')
        pts = pc.get("outline")
        if not isinstance(pts, list) or len(pts) < 3:
            raise PatternError(f'piece "{name}": its outline needs at least 3 points [[x, y], …] (metres)')
        for i, p in enumerate(pts):
            if not isinstance(p, list) or len(p) != 2:
                raise PatternError(f'piece "{name}": outline point {i} is not [x, y]')
        pts = [[_num(c, f'piece "{name}" outline point {i}') for c in p] for i, p in enumerate(pts)]
        m = len(pts)
        for i in range(m):
            if math.dist(pts[i], pts[(i + 1) % m]) < 1e-6:
                raise PatternError(f'piece "{name}": outline points {i} and {(i + 1) % m} are the same point')
            for j in range(i + 2, m):
                if (j + 1) % m != i and _crosses(pts[i], pts[(i + 1) % m], pts[j], pts[(j + 1) % m]):
                    raise PatternError(f'piece "{name}": its outline crosses itself (edge {i} crosses edge {j}); '
                                       "an outline goes once round the piece without crossing")
        if abs(GM.area2(pts)) < 1e-8:
            raise PatternError(f'piece "{name}": its outline encloses no area')
        at = pc.get("at", [0, 0, 0])
        if not isinstance(at, list) or len(at) != 3:
            raise PatternError(f'piece "{name}": "at" is [x, y, z] metres, where its outline\'s origin sits')
        [_num(v, f'piece "{name}" at') for v in at]
        if _num(pc.get("wrap", 0), f'piece "{name}" wrap') < 0:
            raise PatternError(f'piece "{name}": wrap is a radius in metres, 0 (flat) or more')
        _num(pc.get("turn", 0), f'piece "{name}" turn')
        names[name] = m
    used = {}
    for n, sm in enumerate(seams):
        if not isinstance(sm, dict) or set(sm) - SEAM_KEYS or not {"a", "b"} <= set(sm):
            raise PatternError(f'seam {n}: is {{"a": [piece, edge], "b": [piece, edge]}} (and "flip": true to swap its ends)')
        for side in ("a", "b"):
            ref = sm[side]
            if not (isinstance(ref, list) and len(ref) == 2 and isinstance(ref[1], int) and not isinstance(ref[1], bool)):
                raise PatternError(f'seam {n}: "{side}" is [piece name, edge number], not {ref!r}')
            if ref[0] not in names:
                raise PatternError(f'seam {n}: no piece "{ref[0]}" (there are: {", ".join(names) or "none"})')
            if not 0 <= ref[1] < names[ref[0]]:
                raise PatternError(f'seam {n}: piece "{ref[0]}" has edges 0 to {names[ref[0]] - 1}, not {ref[1]} '
                                   "(edge i runs from outline point i to the next)")
            key = tuple(ref)
            if key in used:
                raise PatternError(f'seam {n}: edge {ref[1]} of "{ref[0]}" is sewn already (seam {used[key]}); '
                                   "an edge is sewn to one other edge")
            used[key] = n


def spacing(pieces: list) -> float:
    """The triangle size: about POINTS points over the whole garment (a hex lattice: h² √3/2 per point)."""
    area = sum(abs(GM.area2(pc["outline"])) / 2 for pc in pieces)
    return min(SPACING[1], max(SPACING[0], math.sqrt(area / (POINTS * math.sqrt(3) / 2))))


def _place(pc: dict):
    """The piece's (u, v) → item space function."""
    r, (ax, ay, az) = float(pc.get("wrap", 0)), [float(v) for v in pc.get("at", [0, 0, 0])]
    t = math.radians(float(pc.get("turn", 0)))
    c, s = math.cos(t), math.sin(t)

    def to3(u, v):
        x, z = (r * math.sin(u / r), r * math.cos(u / r) - r) if r > 0 else (u, 0.0)
        return [round(c * x + s * z + ax, 7), round(v + ay, 7), round(-s * x + c * z + az, 7)]
    return to3


def _resample(pts: list, h: float):
    """The outline at spacing ≤ h as one loop, and each edge's loop positions from its first corner to its last."""
    loop, edges = [], []
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n = max(1, math.ceil(math.dist(a, b) / h))
        edges.append([len(loop) + k for k in range(n + 1)])
        loop += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n)]
    edges[-1][-1] = 0
    return loop, edges


def _pairs(a: list, b: list, pts: list, flip) -> list[list[int]]:
    """Seam pairs: the ends that start nearer together are paired (or the other way with flip), then each point of the
    edge with more points to the one on the other edge nearest in arc-length parameter."""
    straight = math.dist(pts[a[0]], pts[b[0]]) + math.dist(pts[a[-1]], pts[b[-1]])
    crossed = math.dist(pts[a[0]], pts[b[-1]]) + math.dist(pts[a[-1]], pts[b[0]])
    if (crossed < straight) != bool(flip):
        b = b[::-1]
    swap = len(b) > len(a)
    many, few = (b, a) if swap else (a, b)
    out = [[p, few[round(i * (len(few) - 1) / (len(many) - 1))]] for i, p in enumerate(many)]
    return [[q, p] for p, q in out] if swap else out


@functools.lru_cache(maxsize=16)
def _made(pieces_text: str, seams_text: str) -> dict:
    pieces, seams = read(pieces_text, "pieces"), read(seams_text, "seams")
    check(pieces, seams)
    if not pieces:
        raise PatternError("the pattern has no pieces yet (garment.piece adds one)")
    h, points, tris, edges = spacing(pieces), [], [], {}
    for pc in pieces:
        flat = [[float(v) for v in p] for p in pc["outline"]]
        loop, ends = _resample(flat, h)
        order = list(range(len(loop))) if GM.area2(flat) > 0 else [0, *range(len(loop) - 1, 0, -1)]
        p2, t2 = GM.triangulate([loop[i] for i in order], h)
        where = {o: k for k, o in enumerate(order)}            # loop position → its point in p2
        to3, base = _place(pc), len(points)
        points += [to3(u, v) for u, v in p2]
        tris += [[base + i for i in t] for t in t2]
        edges[pc["name"]] = [[base + where[k] for k in e] for e in ends]
    pairs = [_pairs(edges[s["a"][0]][s["a"][1]], edges[s["b"][0]][s["b"][1]], points, s.get("flip")) for s in seams]
    return {"points": points, "triangles": tris, "edges": edges, "seams": [p for ps in pairs for p in ps], "spacing": h}


def make(item: dict) -> dict:
    """{points (item space), triangles, edges {piece: [[point, …] per outline edge, as written]}, seams [[i, j], …],
    spacing} of a pattern mesh. Shared and cached: never change what it returns."""
    return _made(item.get("pieces") or "", item.get("seams") or "")


def engine_seams(item: dict) -> list[list[int]]:
    """The seam pairs as the engine numbers the mesh's points: an editable mesh reaches it with each triangle's corners as
    their own points, face by face (core poly.cpp `corners`), so point i is the first corner that names it (the engine
    welds the corners of one place back into one point and carries the pairs along)."""
    made = make(item)
    first: dict[int, int] = {}
    for k, p in enumerate(i for t in made["triangles"] for i in t):
        first.setdefault(p, k)
    return [[first[a], first[b]] for a, b in made["seams"]]


def problems(item: dict) -> list[str]:
    """The document check's words for a pattern mesh (kind.py): empty when it can be made. A pattern is cloth or off."""
    if item.get("simulate", "off") not in ("off", "cloth"):
        return [f'{item["id"]}: a sewing pattern is sewn and draped as cloth: Simulate Cloth (or Off), not '
                f'{item["simulate"]}']
    try:
        pieces = read(item.get("pieces") or "", "pieces")
        if not pieces:
            raise PatternError("a sewing pattern needs at least one piece (script: garment(id, pieces=[…]); or "
                               "garment.make / garment.piece)")
        check(pieces, read(item.get("seams") or "", "seams"))
    except PatternError as e:
        return [f'{item["id"]}: {e}']
    return []
