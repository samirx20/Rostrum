"""How far a clay piece's blend reaches (clay_scene.chain sends the result to the core). A blend is how softly a piece
joins what it TOUCHES; it never reaches across a gap to join a piece it doesn't touch (gaps7 Hello: the head's 4 cm
blend reached the shoulder 1 cm under it, the clay webbed head and arm together, and the raised arm melted into the
head; nobody asked for that join). So an added piece's blend is held under SHARE of its surface gap to the nearest added
piece it doesn't overlap; with nothing near, it is the blend as asked. The document keeps the asked value; only what the
core builds changes. Pieces as balls (pose_body._ends: a sphere, points along a capsule, a drawn or spun piece's balls,
mirrored ones on both sides); a piece made from an item has no balls and keeps its blend.
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


def blends(steps: list[dict]) -> dict[int, float]:
    """{index in steps: the blend the core gets} for the shown added pieces whose blend would reach a piece they don't touch."""
    added = [(n, s, b) for n, s in enumerate(steps) if s.get("step") == "piece" and not s.get("hidden")
             and s.get("mode", "add") == "add" and (b := _balls(s))]
    out = {}
    for n, s, own in added:
        gaps = [g for m, _, other in added if m != n and (g := _gap(own, other)) > TOUCH]
        asked = float(s.get("blend", 0.0))
        if gaps and asked > SHARE * min(gaps):
            out[n] = round(SHARE * min(gaps), 6)
    return out
