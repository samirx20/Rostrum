"""Which part of the rig in hand a press lands on, from the parts' outlines as the engine draws them posed (the engine's
`place` answer: each layer's `edge`, flattened M / L / Z contours in comp px). The canvas's own pick knows a rig only
as one box at rest, so a press on an arm raised out of that box missed the rig (hand maker C, C1). No Qt.
"""
from __future__ import annotations

import re

_CMD = re.compile(r"([MLZ])([^MLZ]*)")
_NUM = re.compile(r"-?[\d.]+(?:e-?\d+)?")


def contours(d: str) -> list[list[tuple[float, float]]]:
    """The closed contours of flattened path data."""
    out, cur = [], []
    for cmd, nums in _CMD.findall(d or ""):
        if cmd == "M" and cur:
            out.append(cur)
            cur = []
        v = [float(n) for n in _NUM.findall(nums)]
        cur += [(v[i], v[i + 1]) for i in range(0, len(v) - 1, 2)]
        if cmd == "Z" and cur:
            out.append(cur)
            cur = []
    return out + ([cur] if cur else [])


def inside(d: str, x: float, y: float) -> bool:
    """(x, y) is inside the outline (even-odd over every contour)."""
    hit = False
    for pts in contours(d):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
            if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                hit = not hit
    return hit


def part_at(order: list[str], edges: dict[str, str], x: float, y: float) -> str:
    """The topmost part (`order`: drawn first to last) whose posed outline holds (x, y), or ""."""
    return next((p for p in reversed(order) if edges.get(p) and inside(edges[p], x, y)), "")


def _off(bone: dict, x: float, y: float) -> float:
    """How far (x, y) is from a posed bone, joint to tip (comp px)."""
    import math
    ax, ay, dx, dy = bone["x"], bone["y"], bone["tipX"] - bone["x"], bone["tipY"] - bone["y"]
    f = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy or 1.0)))
    return math.hypot(x - ax - f * dx, y - ay - f * dy)


def press_target(rig: dict, order: list[str], edges: dict[str, str], posed: list[dict], x: float, y: float,
                 on_rig_at_rest: bool) -> str:
    """What a Move-tool press at (x, y) does on the rig in hand: the bone it poses (the bone the part under the press
    is bound to), "rig" (the part is on the root bone, or bound to none: the whole rig moves), or "" (no part of the
    rig there: the canvas's own pick). With the posed outlines (`edges`) the part is the one drawn there; without them
    (the engine's first answer not in yet) the nearest posed bone, and only inside the rig's box at rest."""
    parent = {b["id"]: b["parent"] for b in rig.get("bones", [])}
    if edges:
        part = part_at(order, edges, x, y)
        if not part:
            return ""
        bone = next((b["bone"] for b in rig.get("binds", []) if b["layer"] == part), "")
    else:
        if not on_rig_at_rest:
            return ""
        near = min((b for b in posed if b["id"] in parent), key=lambda b: _off(b, x, y), default=None)
        bone = near["id"] if near else ""
    return bone if bone in parent and parent[bone] else "rig"
