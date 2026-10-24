"""Cutting an editable mesh's faces (SPEC §4.3): a loop cut across a ring of quads, and the knife's plane cut. Pure
geometry on plain lists, like poly.py; new points on an edge are shared by both faces along it, so the mesh stays
welded (a neighbour that isn't cut gets the point on its edge too).
"""
from __future__ import annotations

from .poly import Change, add, cross, dot, normal, sub, unit


def key(a, b):
    return (min(a, b), max(a, b))


def along(chains, s, t):
    """The points on edge s-t, from s to t (ends included)."""
    c = chains[key(s, t)]
    return c if c[0] == s else c[::-1]


def insert_chains(faces, chains, skip=()) -> list[list[int]]:
    """Every face not in `skip` gets the new points of its cut edges, in its own order."""
    out = []
    for n, f in enumerate(faces):
        g = list(f)
        if n not in skip:
            g = []
            for a, b in zip(f, f[1:] + f[:1]):
                g.append(a)
                if key(a, b) in chains:
                    g += along(chains, a, b)[1:-1]
        out.append(g)
    return out


def _opposite(q, s, t):
    i = q.index(s)
    if q[(i + 1) % 4] == t:
        return q[(i - 1) % 4], q[(i + 2) % 4]
    return q[(i + 1) % 4], q[(i - 2) % 4]


def ring(faces, edge) -> tuple[list[tuple[int, int, int]], dict]:
    """The quads across from `edge`, both ways until a face that isn't a quad, an open border, or back round:
    [(face, s, t)] with s-t the edge it is entered by, and {edge key: its start point} (cuts line up from there)."""
    owners: dict[tuple, list[int]] = {}
    for n, f in enumerate(faces):
        for a, b in zip(f, f[1:] + f[:1]):
            owners.setdefault(key(a, b), []).append(n)
    quads, starts, seen = [], {key(*edge): edge[0]}, set()
    for f in list(owners.get(key(*edge), [])):
        s, t = edge
        while len(faces[f]) == 4 and f not in seen:
            seen.add(f)
            quads.append((f, s, t))
            s, t = _opposite(faces[f], s, t)
            starts.setdefault(key(s, t), s)
            others = [g for g in owners[key(s, t)] if g != f]
            if not others:
                break
            f = others[0]
    return quads, starts


def loopcut(points, faces, edge, count: int = 1, slide: float = 0.0) -> Change:
    """Cut the ring of quads across from `edge` `count` times, evenly (one cut: `slide` -1..1 moves it towards the
    ring's start or end side). The new faces are the selection."""
    quads, starts = ring(faces, edge)
    if not quads:
        raise ValueError(f"edge {edge[0]}-{edge[1]} has no four-sided face next to it to cut across")
    pts, chains = [list(p) for p in points], {}
    ts = [0.5 + 0.49 * slide] if count == 1 else [k / (count + 1) for k in range(1, count + 1)]
    for e, s in starts.items():
        t = e[1] if s == e[0] else e[0]
        ids = []
        for x in ts:
            ids.append(len(pts))
            pts.append(add(points[s], sub(points[t], points[s]), x))
        line = [s, *ids, t]
        chains[e] = line if s == e[0] else line[::-1]
    done = {f for f, _, _ in quads}
    out = insert_chains(faces, chains, skip=done)
    parents, kept = list(range(len(faces))), set()
    for f, s, t in quads:
        so, to = _opposite(faces[f], s, t)
        a, b = along(chains, s, t), along(chains, so, to)
        forward = faces[f][(faces[f].index(s) + 1) % 4] == t
        for k in range(len(a) - 1):
            q = [a[k], a[k + 1], b[k + 1], b[k]] if forward else [a[k + 1], a[k], b[k], b[k + 1]]
            n = f if k == 0 else len(out)
            if k == 0:
                out[f] = q
            else:
                out.append(q)
                parents.append(f)
            kept.add(n)
    return Change(pts, out, parents, chains, kept)


def knife(points, faces, p0, p1, view) -> Change:
    """Cut, right across, every face facing the viewer that the stroke p0-p1 passes over (seen along `view`): the
    plane through the stroke and the view splits it in two. `kept` is the faces cut (empty: nothing was cut)."""
    d = unit(view)
    seg = sub(p1, p0)
    sp = sub(seg, [x * dot(seg, d) for x in d])        # the stroke as seen: its part across the view
    nrm = unit(cross(seg, d))
    if dot(sp, sp) < 1e-18 or dot(nrm, nrm) == 0:
        raise ValueError("the stroke runs along the view direction, so it has no length on screen")
    size = max(max(abs(c) for c in p) for p in points) or 1.0
    eps = 1e-9 * size
    side = [dot(sub(p, p0), nrm) for p in points]
    pts, made, cuts = [list(p) for p in points], {}, {}

    def at(x):
        return dot(sub(x, p0), sp) / dot(sp, sp)
    for n, f in enumerate(faces):
        if dot(normal(points, f), d) >= -1e-9:
            continue
        hits = []                                      # (position in f, point, edge it is on or None)
        for i, (a, b) in enumerate(zip(f, f[1:] + f[:1])):
            if abs(side[a]) <= eps:
                hits.append((i, a, None))
            elif abs(side[b]) > eps and side[a] * side[b] < 0:
                hits.append((i, None, (a, b)))
        if len(hits) != 2 or (hits[0][2] is None and hits[1][2] is None and
                              (hits[1][0] - hits[0][0]) % len(f) in (1, len(f) - 1)):
            continue
        where = []
        for _, v, e in hits:
            if e:
                a, b = e
                v = add(points[a], sub(points[b], points[a]), side[a] / (side[a] - side[b]))
                where.append(at(v))
            else:
                where.append(at(points[v]))
        if max(where) < -1e-6 or min(where) > 1 + 1e-6:
            continue
        cuts[n] = hits
        for _, v, e in hits:
            if e and key(*e) not in made:
                a, b = e
                made[key(*e)] = len(pts)
                pts.append(add(points[a], sub(points[b], points[a]), side[a] / (side[a] - side[b])))
    chains = {e: [e[0], v, e[1]] for e, v in made.items()}
    out = insert_chains(faces, chains, skip=set(cuts))
    parents = list(range(len(faces)))
    for n, hits in cuts.items():
        f, g, marks = faces[n], [], []
        for i, v in enumerate(f):
            if hits[0][1] == v or hits[1][1] == v:
                marks.append(len(g))
            g.append(v)
            for h in hits:
                if h[0] == i and h[2]:
                    marks.append(len(g))
                    g.append(made[key(*h[2])])
        i, j = sorted(marks)
        out[n] = g[i:j + 1]
        out.append(g[j:] + g[:i + 1])
        parents.append(n)
    return Change(pts, out, parents, chains, set(cuts))
