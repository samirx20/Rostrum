"""Selectors: how agents and the screen name points, edges and faces of an editable mesh in one line of text
(SPEC §4.3), so a script needn't depend on face numbers. The selection itself is screen state; operations get a
selector.

    "all"                       every face
    "faces 3 4 9"               by number;  "points 0 1 2";  "edges 0-1 1-5" (an edge by its two points)
    "top" "bottom" "front" "back" "left" "right"
                                the outermost faces facing +y, −y, +z (towards the default camera), −z, +x, −x
    "faces facing +y"           every face within 30° of +y (or "faces facing -x within 10")
    "edges around top"          the border of what a faces selector picks (the loop round the lid's top)
"""
from __future__ import annotations

import math
import re

from .poly import centre, dot, faces_of, normal

KINDS = ("points", "edges", "faces")
AXES = {"+x": [1, 0, 0], "-x": [-1, 0, 0], "+y": [0, 1, 0], "-y": [0, -1, 0], "+z": [0, 0, 1], "-z": [0, 0, -1]}
SIDES = {"top": "+y", "bottom": "-y", "front": "+z", "back": "-z", "right": "+x", "left": "-x"}
FORMS = ["all", "faces 3 4", "points 0 1", "edges 0-1 1-5", *SIDES, "faces facing +y", "faces facing -x within 10",
         "edges around top"]
FACING = re.compile(r"faces facing ([+-][xyz])(?: within (\d+(?:\.\d+)?))?$")


class BadSelector(ValueError):
    pass


def edges_of(item: dict) -> list[tuple[int, int]]:
    """Every edge once, as (a, b) with a < b, in a stable order."""
    seen = set()
    for f in faces_of(item):
        for i, a in enumerate(f):
            b = f[(i + 1) % len(f)]
            seen.add((min(a, b), max(a, b)))
    return sorted(seen)


def face_normal(item: dict, n: int) -> list[float]:
    return normal(item["points"], faces_of(item)[n])


def facing(item: dict, axis: str, within: float = 30.0) -> set[int]:
    a, cos = AXES[axis], math.cos(math.radians(within))
    pts = item["points"]
    return {n for n, f in enumerate(faces_of(item)) if dot(normal(pts, f), a) >= cos - 1e-9}


def side(item: dict, name: str) -> set[int]:
    """The faces facing that way that are furthest out that way (the lid's top, not a step lower down)."""
    a = AXES[SIDES[name]]
    faces, pts = faces_of(item), item["points"]
    cands = facing(item, SIDES[name])
    if not cands:
        return set()
    level = {n: dot(centre(pts, faces[n]), a) for n in cands}
    top = max(level.values())
    span = max(abs(dot(p, a)) for p in pts) or 1.0
    return {n for n, v in level.items() if v >= top - 1e-4 * span}


def parse(selector: str, item: dict) -> tuple[str, set]:
    """(kind, chosen): kind is points / edges / faces; edges are (a, b) pairs with a < b. Fails naming the forms."""
    s = " ".join(str(selector).split()).lower()
    faces = faces_of(item)

    def bad(problem):
        raise BadSelector(f'"{selector}" {problem}. Accepted: ' + " · ".join(f'"{f}"' for f in FORMS))
    if s.startswith("edges around "):
        kind, chosen = parse(s.removeprefix("edges around "), item)
        if kind != "faces":
            bad(f"goes round {kind}; it takes a faces selector")
        sides = [(f[i], f[(i + 1) % len(f)]) for n in chosen for f in [faces[n]] for i in range(len(f))]
        return "edges", {(min(a, b), max(a, b)) for a, b in sides if (b, a) not in set(sides)}
    if s == "all":
        return "faces", set(range(len(faces)))
    if s in SIDES:
        return "faces", side(item, s)
    if m := FACING.match(s):
        return "faces", facing(item, m.group(1), float(m.group(2) or 30))
    head, _, rest = s.partition(" ")
    if head not in KINDS or not rest:
        bad("is not a selector")
    if head == "edges":
        known, out = set(edges_of(item)), set()
        for word in rest.split():
            m = re.fullmatch(r"(\d+)-(\d+)", word)
            if not m:
                bad(f'has "{word}", which is not an edge like 0-1')
            e = tuple(sorted((int(m.group(1)), int(m.group(2)))))
            if e not in known:
                bad(f"names edge {word}, which the mesh doesn't have")
            out.add(e)
        return "edges", out
    if not all(w.isdigit() for w in rest.split()):
        bad("has a word that is not a number")
    nums = {int(w) for w in rest.split()}
    top = len(faces) if head == "faces" else len(item["points"])
    if any(n >= top for n in nums):
        bad(f"names {head[:-1]} {max(nums)}; the mesh has {top} {head} (0 to {top - 1})")
    return head, nums


def points_in(item: dict, kind: str, chosen: set) -> set[int]:
    """The points a selection holds: a face's corners, an edge's ends."""
    if kind == "points":
        return set(chosen)
    if kind == "edges":
        return {v for e in chosen for v in e}
    faces = faces_of(item)
    return {v for n in chosen for v in faces[n]}


def text(kind: str, chosen) -> str:
    """The selector for a screen selection (what the screen passes to an operation)."""
    if kind == "edges":
        return "edges " + " ".join(f"{a}-{b}" for a, b in sorted(chosen))
    return f"{kind} " + " ".join(str(n) for n in sorted(chosen))


def middle(item: dict, kind: str, chosen: set) -> list[float]:
    """Where a selection's gizmo sits: the middle of its points, in the item's own space."""
    return centre(item["points"], points_in(item, kind, chosen))
