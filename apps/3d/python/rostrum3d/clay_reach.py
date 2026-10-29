"""How far a clay piece's blend reaches, decided per pair of pieces (clay_scene.chain sends the result to the core). A blend
is how softly a piece joins what it TOUCHES; it never reaches across a gap to join a piece it doesn't touch (gaps7 Hello:
the head's 4 cm blend reached the shoulder 1 cm under it and the raised arm melted into the head; nobody asked for that
join). So each added piece tells the core, for every earlier added piece it doesn't overlap, that piece's balls and the
most blend it may have toward it (SHARE of their surface gap); the core uses the asked blend everywhere else and eases
down to that near those balls (CONTRACT, clay `pairs`). One number per piece was too coarse: holding the arm off the
head also sharpened the arm's join to the body (the Hello judges' chest crease). The document keeps the asked value.
Pieces as balls (pose_body._ends: a sphere, points along a capsule, a drawn or spun piece's balls, mirrored ones on both
sides); a piece made from an item has no balls and keeps its blend everywhere.
"""
from __future__ import annotations

import math

SHARE = 0.8              # the blend's reach stays under this share of the gap (0.8 cm of 1 cm: a clean crease, no web)
TOUCH = 0.002            # pieces this close (m, in the clay's own space) touch: the blend joins them as asked


def _balls(s: dict) -> list:
    from .pose_body import _ends
    if s.get("shape") == "item" or not (s.get("at") or s.get("plane")):
        return []
    own = _ends(s)
    if s.get("symmetry") == "x":
        own += [([-p[0], p[1], p[2]], r) for p, r in own if abs(p[0]) > 1e-9]
    return own


def _gap(a: list, b: list) -> float:
    return min(math.dist(p, q) - r - s for p, r in a for q, s in b)


def pairs(steps: list[dict]) -> dict[int, list[list[float]]]:
    """{index in steps: [[x, y, z, r, most blend], …]}: the balls of each earlier added piece a shown added piece doesn't
    touch but whose asked blend would reach, with the most blend the core may use toward it."""
    added = [(n, s, b) for n, s in enumerate(steps) if s.get("step") == "piece" and not s.get("hidden")
             and s.get("mode", "add") == "add" and (b := _balls(s))]
    out: dict[int, list[list[float]]] = {}
    for n, s, own in added:
        asked = float(s.get("blend", 0.0))
        for m, _, other in added:
            if m >= n or (g := _gap(own, other)) <= TOUCH or asked <= SHARE * g:
                continue
            most = round(SHARE * g, 6)
            out.setdefault(n, []).extend([round(float(v), 6) for v in p] + [round(float(r), 6), most] for p, r in other)
    return out
