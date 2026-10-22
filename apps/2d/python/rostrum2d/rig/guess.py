"""Bones from part names (RIG.md › Bones from part names, UX_SPEC 3.23): on a rig with no bones whose parts are named
like a body, `rig.guess_bones` proposes a skeleton at the parts' joints, an IK chain on each arm and leg, and binds
every part to its bone (a face part to the head; anything else to the nearest bone). One operation = one undo step;
the person (or agent) then drags any joint that is off (`rig.move_joint`, joints.py).

Joints come from the parts' boxes at rest: each part's long axis runs between the middles of its short sides; the
joint between two parts of a limb is halfway between the points of each axis nearest the other part's centre.
"""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.errors import codes

from .. import boxes
from ..kind import REGISTRY as R
from ..names import display_name
from ..ops_items import new_item
from .bodynames import LIMBS, WORDS, bodylike, part


def _axis(b):
    x0, y0, x1, y1 = b
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return ((x0, cy), (x1, cy)) if x1 - x0 >= y1 - y0 else ((cx, y0), (cx, y1))


def _centre(b):
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def _near(seg, p):
    """The point of a segment nearest p."""
    (ax, ay), (bx, by) = seg
    dx, dy = bx - ax, by - ay
    k = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / ((dx * dx + dy * dy) or 1.0)))
    return ax + k * dx, ay + k * dy


def _far(seg, p):
    a, b = seg
    return a if math.dist(a, p) >= math.dist(b, p) else b


def _mid(a, b):
    return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2


def limb_joints(parts: list, body) -> list:
    """The n + 1 joints of a limb's n part boxes, from the shoulder or hip out."""
    axes = [_axis(b) for b in parts]
    if len(parts) == 1:
        a, b = axes[0]
        start = a if math.dist(a, body) <= math.dist(b, body) else b
        return [start, b if start == a else a]
    out = [_far(axes[0], _centre(parts[1]))]
    for i in range(1, len(parts)):
        out.append(_mid(_near(axes[i - 1], _centre(parts[i])), _near(axes[i], _centre(parts[i - 1]))))
    return out + [_far(axes[-1], _centre(parts[-2]))]


def _bone(name, parent, a, b):
    return {"name": name, "parent": parent, "x": round(a[0], 2), "y": round(a[1], 2),
            "angle": round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])), 2), "length": round(math.dist(a, b), 2)}


def _dist_to(bone, p):
    a = (bone["x"], bone["y"])
    t = math.radians(bone["angle"])
    return math.dist(_near((a, (a[0] + bone["length"] * math.cos(t), a[1] + bone["length"] * math.sin(t))), p), p)


def plan(layers: list[dict], t: float = 0.0) -> dict:
    """{"bones": [{name, parent name, x, y, angle, length}], "iks": [{name, bone name, bend}], "binds": [{layer, bone
    name}]} for a rig's layers (rig px, at rest)."""
    found = {}
    for lay in layers:
        p = part(display_name(lay))
        if p:
            found.setdefault(p, []).append(lay)
    box = {lay["id"]: boxes.box(lay, t) for lay in layers}
    first = lambda role: next((found[k][0] for k in found if k[0] == role), None)   # noqa: E731
    torso, hip, head, neck = first("torso"), first("hip"), first("head"), first("neck")
    every = boxes.extent([c for b in box.values() for c in ((b[0], b[1]), (b[2], b[3]))])
    trunk = box[torso["id"]] if torso else every
    body = _centre(trunk)
    root = _centre(box[hip["id"]]) if hip else ((trunk[0] + trunk[2]) / 2, trunk[3])
    top = ((trunk[0] + trunk[2]) / 2, trunk[1]) if torso else \
        ((box[head["id"]][0] + box[head["id"]][2]) / 2, box[head["id"]][3]) if head else (root[0], root[1] - 100)
    bones, iks, binds, of = [_bone("body", "", root, top)], [], [], {}
    for lay in (torso, hip):
        if lay:
            of[lay["id"]] = "body"
    up = "body"
    if neck:
        nb = box[neck["id"]]
        bones.append(_bone("neck", "body", top, ((nb[0] + nb[2]) / 2, nb[1])))
        up, top, of[neck["id"]] = "neck", ((nb[0] + nb[2]) / 2, nb[1]), "neck"
    if head:
        hb = box[head["id"]]
        bones.append(_bone("head", up, ((hb[0] + hb[2]) / 2, hb[3]), ((hb[0] + hb[2]) / 2, hb[1])))
        of[head["id"]] = "head"
    for side in ("L", "R", ""):
        for limb, roles in LIMBS.items():
            have = [found[(r, side)][0] for r in roles if (r, side) in found]
            if not have:
                continue
            joints = limb_joints([box[lay["id"]] for lay in have], body)
            parent = "body"
            for lay, a, b in zip(have, joints, joints[1:]):
                name = " ".join(w for w in (WORDS[part(display_name(lay))[0]], side) if w)
                bones.append(_bone(name, parent, a, b))
                parent = of[lay["id"]] = name
            if len(have) >= 2:
                (ax, ay), (bx, by), (cx, cy) = joints[:3]
                turn = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
                bend = ("clockwise" if turn > 0 else "counterclockwise") if abs(turn) > 1e-3 * math.dist(joints[0], joints[2]) ** 2 \
                    else ("clockwise" if joints[0][0] < body[0] else "counterclockwise")
                iks.append({"name": f"{limb} {side} IK".replace("  ", " "), "bone": bones[-len(have) + 1]["name"], "bend": bend})
    for lay in layers:
        bone = of.get(lay["id"]) or ("head" if head and (part(display_name(lay)) or ("",))[0] == "face" else None)
        bone = bone or min(bones, key=lambda b: _dist_to(b, _centre(box[lay["id"]])))["name"]
        binds.append({"layer": lay["id"], "bone": bone})
    return {"bones": bones, "iks": iks, "binds": binds}


def guessable(rig: dict | None) -> bool:
    """A rig with no bones whose parts are named like a body: the context bar offers Bones from part names."""
    return bool(rig) and rig.get("type") == "rig" and not rig.get("bones") and \
        bodylike([display_name(lay) for lay in rig.get("layers", [])])


@R.operation("rig.guess_bones", "Propose a skeleton from the rig's part names (upper arm L, forearm, hand, thigh, shin, "
             "foot, head, torso …): a bone at each part's joints, an IK chain on each arm and leg, and every part bound "
             "to its bone (face parts to the head, others to the nearest bone). Only on a rig with no bones yet.",
             target="rig", label="Bones from part names",
             params=[Param.toggle("ik", label="IK on arms and legs", default=True,
                                  help="Drag a hand or a foot and the limb bends to reach")])
def rig_guess_bones(ctx, targets, args):
    for t in targets:
        rig = ctx.item(t)
        names = [display_name(lay) for lay in rig.get("layers", [])]
        if rig.get("bones"):
            ctx.fail(codes.CONFLICT, t, "already has bones", hint="Drag its joints to fix them, or delete its bones first (bone.remove).")
        if not bodylike(names):
            ctx.fail(codes.BAD_ARGUMENT, t, "has no parts named like a body", names,
                     hint='Name the parts "head", "torso", "upper arm L", "forearm L", "hand L", "thigh R" …')
        p, ids = plan(rig["layers"]), {}
        planned = {b["name"]: b for b in p["bones"]}
        for b in p["bones"]:
            item = new_item(ctx, "bone", {"name": b["name"]})
            item.update({k: v for k, v in b.items() if k != "name"}, parent=ids.get(b["parent"], ""))
            ids[b["name"]] = item["id"]
            ctx.insert(t, "bones", item)
        for k in p["iks"] if args.get("ik", True) else []:
            item = new_item(ctx, "ik", {"name": k["name"]})
            bone = planned[k["bone"]]
            tip = (bone["x"] + bone["length"] * math.cos(math.radians(bone["angle"])),
                   bone["y"] + bone["length"] * math.sin(math.radians(bone["angle"])))
            item.update(bone=ids[k["bone"]], bend=k["bend"], targetX=round(tip[0], 2), targetY=round(tip[1], 2))
            ctx.insert(t, "iks", item)
        for b in p["binds"]:
            item = new_item(ctx, "bind", {"name": f"{display_name(ctx.item(b['layer']))} → {b['bone']}"})
            item.update(layer=b["layer"], bone=ids[b["bone"]])
            ctx.insert(t, "binds", item)
