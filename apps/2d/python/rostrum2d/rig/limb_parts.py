"""The shapes limb() draws (guide character-rigging-and-lip-sync, "Limbs that read in a still"): a limb that tapers
(thick at the shoulder or hip, thinner at the elbow or knee, the forearm or calf swelling a little below it and thin at
the wrist or ankle), a joint shape at the elbow / knee, and an outline that separates a forearm crossing in front of
the body. All are plain path / shape layers a person edits as usual; sizes and colours stay the caller's.

The outline is a closed path in the layer's own px, the limb running down its box (local +y = the limb's direction,
the layer turned by angle - 90 as limb() places it), sampled densely enough that a bend bind's mesh bends it smoothly.
"""
from __future__ import annotations

import math

JOINTS = ("round", "ball", "none")
CAP_STEPS, SIDE_STEPS = 10, 6                # outline points per end cap / per station gap
SHADE = 0.42                                 # an automatic outline: the fill this much darker


def stations(lens, wid, taper: float) -> list[tuple[float, float]]:
    """(distance from the shoulder along the limb, width) from the shoulder to the wrist: upper wid[0] narrowing by
    taper/2 to the joint, the lower part swelling back to wid[1] a third of the way down, then narrowing by `taper`."""
    l0, l1 = lens[0], lens[1]
    joint = min(wid[0] * (1 - taper / 2), wid[1])
    return [(0.0, wid[0]), (l0, joint), (l0 + l1 / 3, wid[1]), (l0 + l1, wid[1] * (1 - taper))]


def outline(st: list[tuple[float, float]]) -> tuple[float, float, str, float]:
    """A closed outline round the stations, with round ends: (box w, box h, path data in box px, the first station's
    distance from the box's top)."""
    w = max(s[1] for s in st)
    r0, r1 = st[0][1] / 2, st[-1][1] / 2
    top = r0
    h = top + st[-1][0] + r1
    cx = w / 2
    right, left = [], []
    for (a, wa), (b, wb) in zip(st, st[1:]):
        for i in range(SIDE_STEPS):
            u = i / SIDE_STEPS
            y, r = top + a + (b - a) * u, (wa + (wb - wa) * u) / 2
            right.append((cx + r, y))
            left.append((cx - r, y))
    right.append((cx + r1, top + st[-1][0]))
    left.append((cx - r1, top + st[-1][0]))
    pts = list(right)
    for i in range(1, CAP_STEPS):                    # the wrist's round end, right side round to left
        a = math.pi * i / CAP_STEPS
        pts.append((cx + r1 * math.cos(a), top + st[-1][0] + r1 * math.sin(a)))
    pts += reversed(left)
    for i in range(1, CAP_STEPS):                    # the shoulder's round end, left side over to right
        a = math.pi + math.pi * i / CAP_STEPS
        pts.append((cx + r0 * math.cos(a), top + r0 * math.sin(a)))
    d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in pts) + " Z"
    return w, h, d, top


def piece(build, id_, bx, by, angle, st, fill, at=0.0):
    """A tapered piece along `angle` whose first station sits `at` px from the joint (bx, by): a path layer."""
    w, h, d, top = outline([(s - st[0][0], v) for s, v in st])
    a = math.radians(angle)
    k = at + h / 2 - top                             # the box's middle, from the joint, along the limb
    return build.layer("path", id_, d=d, w=round(w, 2), h=round(h, 2), x=round(bx + math.cos(a) * k, 2),
                       y=round(by + math.sin(a) * k, 2), rotation=angle - 90, fill=fill)


def joint_shape(build, id_, x, y, size, fill):
    """The round at the elbow or knee (a circle centred on the joint)."""
    return build.layer("shape", id_, shape="ellipse", x=round(x, 2), y=round(y, 2), w=round(size, 2), h=round(size, 2),
                       fill=fill)


def darker(hex_: str, k: float = SHADE) -> str:
    """#rrggbb `k` of the way to black (a plain colour; anything else gives a dark grey)."""
    s = hex_.lstrip("#") if isinstance(hex_, str) else ""
    if len(s) not in (6, 8) or any(c not in "0123456789abcdefABCDEF" for c in s[:6]):
        return "#2a2a2a"
    return "#" + "".join(f"{round(int(s[i:i + 2], 16) * (1 - k)):02x}" for i in (0, 2, 4))


def outline_parts(parts, color, width) -> None:
    """Turn the outline on for every part, in `color` (None: each part's fill, darker)."""
    for p in parts:
        n = p.node
        n.update(stroke=True, strokeColor=color or darker(n.get("fill", "")), strokeWidth=round(width, 2))
