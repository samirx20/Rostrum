"""Which clay step made the surface at a spot, and the nearest joint (SPEC § 6, look_at / look_frame highlight).

Worked out from the steps as data, never from the core: each step's own shape is measured against the spot (in the
clay's own space, at rest) as a distance, and the step nearest it made the surface there. numpy, many spots at once.

- A sphere or capsule: how far the spot is from its surface (inside or out).
- A drawn outline: the outline puffed both ways along its plane's normal (round: as thick in the middle as it is wide);
  outside the outline, the distance to its edge.
- A spun profile: the distance to the profile in the (distance from the axis, height) plane.
- A stroke: its dabs (a file, inline dabs, or an agent's path: the ray from each point along `dir`); a spot within the
  brush's radius of a dab was touched by it (distance 0).
- A mirrored step (Mirror x) counts on both sides: the spot is tried as it is and mirrored across X = 0.
- Close calls (within a few mm, TIE of the clay's size) go to the later step: it was made on top. A hidden step, or one
  made from another item (no shape known here), is left out.
"""
from __future__ import annotations

import numpy as np

from . import clay_shapes as G

TIE, TIE_MIN = 0.015, 0.002      # close calls: within this share of the clay's size, at least TIE_MIN metres
INF = np.inf


def _seg(p, a, b):
    """Distance from each point p (N, 3) to the segment a–b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    ab = b - a
    t = np.clip((p - a) @ ab / max(float(ab @ ab), 1e-30), 0.0, 1.0)
    return np.linalg.norm(p - (a + t[:, None] * ab), axis=1)


def _edge2(x, y, poly):
    """(distance to the closed 2-D polygon's edge, inside by even-odd) for points (x, y)."""
    a = np.asarray(poly, float)
    b = np.roll(a, -1, axis=0)
    d = b - a
    px, py = x[:, None] - a[:, 0], y[:, None] - a[:, 1]
    t = np.clip((px * d[:, 0] + py * d[:, 1]) / np.maximum((d * d).sum(1), 1e-30), 0.0, 1.0)
    edge = np.hypot(px - t * d[:, 0], py - t * d[:, 1]).min(axis=1)
    cross = (a[:, 1] > y[:, None]) != (b[:, 1] > y[:, None])
    with np.errstate(divide="ignore", invalid="ignore"):
        xs = a[:, 0] + (y[:, None] - a[:, 1]) * d[:, 0] / d[:, 1]
    inside = (cross & (x[:, None] < xs)).sum(axis=1) % 2 == 1
    return edge, inside


def _outline(p, step):
    pl = step["plane"]
    o, u, v = (np.asarray(pl[i:i + 3], float) for i in (0, 3, 6))
    w = p - o
    x, y, z = w @ u, w @ v, np.abs(w @ np.cross(u, v))
    edge, inside = _edge2(x, y, step["outline"])
    fat = step.get("_fat") or G.inner_radius(step["outline"]) or 1e-6
    e = np.minimum(edge, fat)
    half = float(step.get("puff", 1.0)) * np.sqrt(np.maximum(0.0, e * (2 * fat - e)))   # round: a circle's height
    inner = np.where(z > half, z - half, -np.minimum(edge, half - z))
    return np.where(inside, inner, np.hypot(edge, z))


def _spin(p, step):
    pl, prof = step["plane"], step["profile"]
    o, v = np.asarray(pl[:3], float), np.asarray(pl[6:], float)
    w = p - o
    h = w @ v
    r = np.linalg.norm(w - h[:, None] * v, axis=1)
    edge, inside = _edge2(r, h, [[0.0, prof[0][1]], *prof, [0.0, prof[-1][1]]])
    return np.where(inside, -edge, edge)


def _stroke(p, step, dabs):
    size = float(step.get("size", 0.03))
    if step.get("path"):
        d = np.asarray(G.unit(step.get("dir") or [0, 0, -1]) or [0.0, 0.0, -1.0])
        best = np.full(len(p), INF)
        for a in np.asarray(step["path"], float):        # the ray each path point casts along dir
            t = np.maximum(0.0, (p - a) @ d)
            best = np.minimum(best, np.linalg.norm(p - (a + t[:, None] * d), axis=1))
        return np.maximum(0.0, best - size)
    rows = step.get("dabList") or (dabs(step["dabs"]) if dabs and step.get("dabs") else [])
    if not rows:
        return np.full(len(p), INF)
    r = np.asarray([row[:3] for row in rows], float)
    radius = size * np.asarray([row[9] if len(row) > 9 else 1.0 for row in rows])
    best = np.full(len(p), INF)
    for s in range(0, len(r), 256):                     # in chunks: points × dabs
        dd = np.linalg.norm(p[:, None, :] - r[None, s:s + 256], axis=2) - radius[None, s:s + 256]
        best = np.minimum(best, dd.min(axis=1))
    return np.maximum(0.0, best)


def distance(p, step, dabs=None):
    """How far each spot of p ((N, 3) clay space) is from what `step` made: 0 on its surface, negative inside a piece,
    inf when not known here. `dabs(ref)` reads a stroke's dabs file (None: strokes kept in a file are left out)."""
    p = np.atleast_2d(np.asarray(p, float))
    shape = step.get("shape", "sphere")
    if step.get("step") == "stroke":
        f = lambda q: _stroke(q, step, dabs)  # noqa: E731
    elif shape == "sphere" and step.get("at"):
        f = lambda q: np.linalg.norm(q - np.asarray(step["at"], float), axis=1) - step.get("radius", 0.1)  # noqa: E731
    elif shape == "capsule" and step.get("at") and step.get("to"):
        f = lambda q: _seg(q, step["at"], step["to"]) - step.get("radius", 0.1)  # noqa: E731
    elif shape == "outline" and len(step.get("plane") or []) == 9 and len(step.get("outline") or []) >= 3:
        f = lambda q: _outline(q, step)  # noqa: E731
    elif shape == "spin" and len(step.get("plane") or []) == 9 and len(step.get("profile") or []) >= 2:
        f = lambda q: _spin(q, step)  # noqa: E731
    else:
        return np.full(len(p), INF)
    d = f(p)
    if step.get("symmetry") == "x":
        m = f(p * [-1.0, 1.0, 1.0])
        d = np.where(np.abs(m) < np.abs(d), m, d)
    return d


def kind(step) -> str:
    """'drawn', 'spun', 'sphere', 'capsule', 'from an item', 'carved sphere', 'add stroke' …"""
    if step.get("step") == "stroke":
        return f'{step.get("brush", "add")} stroke'
    shape = step.get("shape", "sphere")
    k = {"outline": "drawn", "spin": "spun", "item": "from an item"}.get(shape, shape)
    return f"carved {k}" if step.get("mode") == "carve" else k


def label(step) -> str:
    """'arm, drawn': the step's name (else its id) and its kind."""
    return f'{step.get("name") or step["id"]}, {kind(step)}'


def live(steps: list[dict]) -> list[dict]:
    """The steps that count (not hidden), drawn ones with their fatness measured once."""
    return [{**s, "_fat": G.inner_radius(s["outline"])} if s.get("shape") == "outline" and s.get("outline") else s
            for s in steps if not s.get("hidden")]


def owners(steps: list[dict], p, dabs=None) -> tuple[np.ndarray, np.ndarray]:
    """For each spot of p ((N, 3) clay space, rest): the index into `steps` (from `live`) of the step that made the
    surface there (-1: none measurable) and how far that step's shape is."""
    p = np.atleast_2d(np.asarray(p, float))
    if not steps:
        return np.full(len(p), -1), np.full(len(p), INF)
    d = np.abs(np.stack([distance(p, s, dabs) for s in steps]))          # (steps, N)
    best = d.min(axis=0)
    size = float(np.ptp(p, axis=0).max()) if len(p) > 1 else 0.0
    from .clay_detail import bounds
    ball = bounds({"steps": steps})
    tie = max(TIE_MIN, TIE * (ball[1] * 2 if ball else size))
    close = d <= (best + tie)[None, :]
    idx = len(steps) - 1 - np.argmax(close[::-1], axis=0)               # the latest close step
    idx = np.where(np.isfinite(best), idx, -1)
    return idx, np.where(idx >= 0, d[np.maximum(idx, 0), np.arange(len(p))], INF)


def find(steps: list[dict], p, dabs=None) -> dict | None:
    """The step that made the surface at one spot p: {id, name, kind, label, distance}; None when none is measurable."""
    ss = live(steps)
    i, d = owners(ss, [p], dabs)
    if i[0] < 0:
        return None
    s = ss[int(i[0])]
    return {"id": s["id"], "name": s.get("name") or "", "kind": kind(s), "label": label(s), "distance": round(float(d[0]), 5)}


def match(steps: list[dict], names: list[str]) -> tuple[set[str], list[str]]:
    """The ids of the steps named (by name or id) and the names that match none."""
    ids, missing = set(), []
    for n in names:
        hit = {s["id"] for s in steps if n in (s["id"], s.get("name"))}
        ids |= hit
        if not hit:
            missing.append(n)
    return ids, missing


def nearest_joint(joints: list[dict], p) -> dict | None:
    """{joint, distance} of the joint whose bone (head → tail, clay space) passes nearest p; None without joints."""
    if not joints:
        return None
    q = np.atleast_2d(np.asarray(p, float))
    d, j = min((float(_seg(q, j["head"], j["tail"])[0]), j["joint"]) for j in joints)
    return {"joint": j, "distance": round(d, 4)}
