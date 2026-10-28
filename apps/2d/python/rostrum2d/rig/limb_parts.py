"""The shapes limb() draws (guide character-rigging-and-lip-sync, "Limbs that read in a still"): a limb that tapers
(thick at the shoulder or hip, thinner at the elbow or knee, the forearm or calf swelling a little below it and thin at
the wrist or ankle), a joint shape at the elbow / knee, a mitten hand (an oval palm with a thumb), and an outline that separates a forearm crossing in front of
the body. All are plain path / shape layers a person edits as usual; sizes and colours stay the caller's.

The outline is a closed path in the layer's own px, the limb running down its box (local +y = the limb's direction,
the layer turned by angle - 90 as limb() places it), sampled densely enough that a bend bind's mesh bends it smoothly.
"""
from __future__ import annotations

import math

JOINTS = ("round", "ball", "none")
CAP_STEPS, SIDE_STEPS = 10, 6                # outline points per end cap / per station gap
SHADE = 0.42                                 # an automatic outline: the fill this much darker
HAND_STEPS, HAND_OVERLAP = 40, 0.18          # outline points of a mitten hand; how far its palm starts above the wrist
HAND_LONG = 1.25                             # a mitten hand at least this x its width long
THUMB, THUMB_AT, THUMB_SPREAD = 0.42, 0.7, 0.42   # the thumb: how far it swells out (share of the palm), where (radians
                                             # from the palm's side toward the wrist), how wide


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


def piece(id_, bx, by, angle, st, at=0.0) -> tuple[str, str, dict]:
    """A tapered piece along `angle` whose first station sits `at` px from the joint (bx, by): a path layer."""
    w, h, d, top = outline([(s - st[0][0], v) for s, v in st])
    a = math.radians(angle)
    k = at + h / 2 - top                             # the box's middle, from the joint, along the limb
    return "path", id_, dict(d=d, w=round(w, 2), h=round(h, 2), x=round(bx + math.cos(a) * k, 2),
                             y=round(by + math.sin(a) * k, 2), rotation=angle - 90)


def joint_shape(id_, x, y, size) -> tuple[str, str, dict]:
    """The round at the elbow or knee (a circle centred on the joint)."""
    return "shape", id_, dict(shape="ellipse", x=round(x, 2), y=round(y, 2), w=round(size, 2), h=round(size, 2))


def mitten(id_, wx, wy, ea, w, length, side) -> tuple[str, str, dict]:
    """A hand that reads as one at a glance: an oval palm `w` wide and `length` long from the wrist (wx, wy) along `ea`,
    a thumb swelling out of its `side` (+1: the hand's own +x, -1: the other) near the wrist. One closed outline."""
    a, b = w / 2, length / 2
    cy = b - HAND_OVERLAP * length                   # the palm's middle from the wrist (it starts a little above it)
    t0 = -THUMB_AT if side > 0 else math.pi + THUMB_AT
    pts = []
    for i in range(HAND_STEPS):
        t = 2 * math.pi * i / HAND_STEPS
        dt = math.atan2(math.sin(t - t0), math.cos(t - t0))
        r = 1 + THUMB * math.exp(-(dt / THUMB_SPREAD) ** 2)
        pts.append((a * r * math.cos(t), cy + b * r * math.sin(t)))
    x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
    x1, y1 = max(p[0] for p in pts), max(p[1] for p in pts)
    d = "M " + " L ".join(f"{x - x0:.2f} {y - y0:.2f}" for x, y in pts) + " Z"
    mx, my, e = (x0 + x1) / 2, (y0 + y1) / 2, math.radians(ea)
    cx_, cy_ = wx + mx * math.sin(e) + my * math.cos(e), wy - mx * math.cos(e) + my * math.sin(e)   # local +x, +y on screen
    return "path", id_, dict(d=d, w=round(x1 - x0, 2), h=round(y1 - y0, 2), x=round(cx_, 2), y=round(cy_, 2), rotation=ea - 90)


def shapes(g: dict, wid) -> list[dict]:
    """A limb's shapes for widths `wid`, bottom to top, as {type, id, fields, bone, bone2, soft, under}: a "round" joint
    (under: it goes below the limb), the limb (one bending piece, or one per bone), a "ball" joint, the hand or foot.
    `g` is what limb() fixed: id, kind, pieces, joint, joint_size, hand, at, angle, ea, lens, taper, wrist, thumb."""
    if g["pieces"] == "none":
        return []
    id_, (bx, by), angle, lens, ea = g["id"], g["at"], g["angle"], g["lens"], g["ea"]
    st = stations(lens, wid, g["taper"])
    out = []
    if g["pieces"] == "bend":
        out.append((piece(id_, bx, by, angle, st), "upper", "lower", max(0.6 * st[1][1], 6.0)))
    else:
        for bone, s_, at in (("upper", st[:2], 0.0), ("lower", st[1:], lens[0])):
            out.append((piece(f"{id_}_{bone}_part", bx, by, angle, s_, at=at), bone, None, None))
    if g["joint"] != "none":
        a = math.radians(angle)
        out.append((joint_shape(f"{id_}_joint", bx + math.cos(a) * lens[0], by + math.sin(a) * lens[0],
                                g["joint_size"] * max(st[1][1], st[2][1])), "lower", None, None))
    if g["wrist"] is not None:
        (wx, wy), e = g["wrist"], math.radians(ea)
        if g["kind"] == "leg":
            end = ("shape", f"{id_}_foot", dict(shape="rect", x=wx + math.cos(e) * lens[2] / 2, y=wy + math.sin(e) * lens[2] / 2,
                                                w=lens[2] + wid[2], h=wid[2], radius=wid[2] / 2, rotation=ea))
        elif g["hand"] == "ball":
            end = ("shape", f"{id_}_hand", dict(shape="ellipse", x=wx + math.cos(e) * lens[2] * 0.5,
                                                y=wy + math.sin(e) * lens[2] * 0.5, w=wid[2], h=wid[2]))
        else:
            end = mitten(f"{id_}_hand", wx, wy, ea, wid[2], max(HAND_LONG * wid[2], lens[2] + 0.6 * wid[2]), g["thumb"])
        out.append((end, "end", None, None))
    return [{"type": t, "id": i, "fields": f, "bone": b, "bone2": b2, "soft": sf,
             "under": i == f"{id_}_joint" and g["joint"] == "round"} for (t, i, f), b, b2, sf in out]


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
