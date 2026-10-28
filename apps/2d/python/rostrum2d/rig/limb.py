"""limb() in a script: an arm or leg made in one go (bones, IK, the shapes and their binds); guide
character-rigging-and-lip-sync, "Limbs that read in a still". The motion calls (walk, idle, pose …) are in motion.py.
"""
from __future__ import annotations

import math

from . import limb_parts as parts_mod
from .model import start_bone, tip

LIMB_KINDS = ("arm", "leg")
PIECES = ("bend", "parts", "none")
PLACEHOLDER = "#d9d9d9"                      # a limb's colour until the end of the script finds its body's
RELAX = {"arm": 20.0, "leg": 6.0}            # degrees the elbow / knee is bent at rest (relax=0: straight)
SIDES = {"right": 0.0, "down": 90.0, "left": 180.0, "up": 270.0}


class Limb:
    """What limb() made: `upper`, `lower`, `end` (bones; `end` is None with no third length), `ik` (the chain on the
    lower bone, or None), `parts` (the shapes: the limb, its joint, its hand / foot), `out` (+1 or -1: the sign of
    `rotation` that swings it away from the body). `reach({t: (x, y)})` keys the IK target in rig px;
    `pose({t: angle})` keys the upper bone's turn; `set(fill=…)` sets fields on every part."""

    def __init__(self, id_, kind, upper, lower, end, ik, parts, out=1):
        self.id, self.kind, self.upper, self.lower, self.end, self.ik, self.parts = id_, kind, upper, lower, end, ik, parts
        self.out = out

    def reach(self, keys: dict, ease: str = "smooth") -> "Limb":
        if self.ik is None:
            raise ValueError(f"{self.id}.reach(…): this limb has no IK chain; make it with limb(…, ik=True)")
        xs, ys = {}, {}
        for t, v in keys.items():
            (x, y), e = (v[0], v[1] if len(v) > 1 else ease) if isinstance(v[0], (tuple, list)) else (v, ease)
            xs[t], ys[t] = (x, e), (y, e)
        self.ik.key("targetX", xs).key("targetY", ys)
        return self

    def pose(self, keys: dict, ease: str = "smooth") -> "Limb":
        """{t: upper turn} or {t: {"upper": a, "lower": b, "end": c}}: rotation keys on those bones. With natural=True
        (the default) the elbow / knee bend that follows the swing is added at the end of the script, so the upper
        turn alone gives a living arm; a "lower" value adds to that bend."""
        per = {}
        for t, v in keys.items():
            v, e = (v[0], v[1]) if isinstance(v, tuple) else (v, ease)
            for part, a in (v.items() if isinstance(v, dict) else (("upper", v),)):
                if part not in ("upper", "lower", "end") or (part == "end" and self.end is None):
                    raise ValueError(f'{self.id}.pose: "{part}" is not one of upper, lower{", end" if self.end else ""}')
                per.setdefault(part, {})[t] = (a, e)
        for part, k in per.items():
            getattr(self, part).key("rotation", k)
        return self

    def set(self, **fields) -> "Limb":
        for p in self.parts:
            p.set(**fields)
        return self

    def __repr__(self):
        return f"limb {self.id} ({self.kind}: {self.upper.id} › {self.lower.id}{' › ' + self.end.id if self.end else ''})"


def bend_way(angle: float, bend: str, where: str) -> str:
    """An IK bend: clockwise / counterclockwise as given, or the screen side the joint should point to (left, right,
    up, down) for a limb whose rest direction is `angle` (clockwise puts the joint at angle - 90)."""
    if bend in ("clockwise", "counterclockwise"):
        return bend
    if bend not in SIDES:
        raise ValueError(f'limb {where}: bend "{bend}" is not one of clockwise, counterclockwise, {", ".join(SIDES)}')
    return "clockwise" if math.cos(math.radians(angle - 90 - SIDES[bend])) > 0 else "counterclockwise"


def make(build, rig, limbs: list, id, x=None, y=None, angle=90, lengths=(120, 110, 30), widths=(40, 30, 44), parent=None,
         kind="arm", ik=None, bend=None, pieces="bend", color=None, end_color=None, end_angle=None, soft=None, relax=None,
         natural=True, taper=0.3, joint="round", joint_size=1.12, outline=True, outline_width=None) -> Limb:
    """script limb(): see the guide and server.py's script tool description. Appends what the end-of-script pass needs
    (colour, outline, the natural bend) to `limbs`."""
    if kind not in LIMB_KINDS:
        raise ValueError(f'limb {id}: kind "{kind}" is not one of {", ".join(LIMB_KINDS)}')
    if pieces not in PIECES:
        raise ValueError(f'limb {id}: pieces "{pieces}" is not one of {", ".join(PIECES)}')
    if joint not in parts_mod.JOINTS:
        raise ValueError(f'limb {id}: joint "{joint}" is not one of {", ".join(parts_mod.JOINTS)}')
    if not 0 <= float(taper) < 1:
        raise ValueError(f"limb {id}: taper {taper} must be from 0 (even) up to below 1")
    lens = tuple(float(v) for v in lengths) + (0.0,) * (3 - len(lengths))
    wid = tuple(float(v) for v in widths) + (widths[-1],) * (3 - len(widths))
    if lens[0] <= 0 or lens[1] <= 0:
        raise ValueError(f"limb {id}: the first two lengths (upper, lower) must be above 0, not {lengths}")
    pid = getattr(parent.upper if isinstance(parent, Limb) else parent, "id", parent) or ""
    start = start_bone(rig["bones"], {"parent": pid, **({"x": x} if x is not None else {}), **({"y": y} if y is not None else {})})
    if "x" not in start or "y" not in start:
        raise ValueError(f"limb {id}: give x, y (the shoulder or hip joint, rig px), or a parent to start at its tip")
    bx, by = float(start["x"]), float(start["y"])
    par = next((b for b in rig["bones"] if b["id"] == pid), None)
    mid = float(par["x"]) if par is not None and abs(float(par["x"]) - bx) > 1e-6 else float(rig.get("w", 0)) / 2
    side = bend if bend is not None else "out" if kind == "arm" else "right"
    if side in ("out", "in"):               # away from / toward the body: the parent bone's pivot, else the rig's middle
        side = ("right" if bx >= mid else "left") if side == "out" else ("left" if bx >= mid else "right")
    way = bend_way(angle, side, id)
    sign = 1.0 if way == "clockwise" else -1.0         # + rotation on the lower bone folds the joint toward `side`
    from .script import for_script as rig_calls        # the bone calls, as a script writes them (bone / ik / bind)
    calls = rig_calls(build)
    upper = calls["bone"](f"{id}_upper", parent=pid, x=bx, y=by, angle=angle, length=lens[0])
    lower = calls["bone"](f"{id}_lower", parent=upper, length=lens[1])
    ea = end_angle if end_angle is not None else (0.0 if kind == "leg" else angle)
    end = calls["bone"](f"{id}_end", parent=lower, angle=ea, length=lens[2]) if lens[2] > 0 else None
    has_ik = ik if ik is not None else kind == "leg"
    chain = calls["ik"](f"{id}_ik", bone=lower, bend=way) if has_ik else None
    rlx = float(relax if relax is not None else RELAX[kind])
    if rlx and not has_ik:                  # the rest pose: joint bent (natural: put by the end-of-script pass, so keys
        if not natural:                     # on the lower bone stay turns from the relaxed bend), the upper bone turned
            lower.node["rotation"] = round(sign * rlx, 3)          # back half so the hand or foot stays under the joint
        upper.node["rotation"] = round(-sign * rlx / 2, 3)
    auto_color = color is None
    color = PLACEHOLDER if auto_color else color
    parts = _parts(build, calls, id, kind, pieces, joint, joint_size, (bx, by), angle, ea, lens, wid, float(taper),
                   (upper, lower, end), color, end_color, soft)
    out = (-1 if math.sin(math.radians(angle)) >= 0 else 1) * (1 if bx >= mid else -1)   # tip moves away from mid
    made = Limb(id, kind, upper, lower, end, chain, parts, out=int(out))
    limbs.append({"limb": made, "rig": rig, "relax": rlx if not has_ik else 0.0, "sign": sign,
                  "auto_color": auto_color and end_color is None, "natural": natural and not has_ik,
                  "outline": None if outline is True else outline,
                  "outline_width": float(outline_width) if outline_width is not None else max(2.0, 0.1 * wid[0])})
    return made


def _parts(build, calls, id, kind, pieces, joint, joint_size, at, angle, ea, lens, wid, taper, bones, color, end_color, soft):
    """The limb's shapes, bottom to top: a "round" joint, the limb (one bending piece, or one per bone), a "ball"
    joint, then the hand or foot."""
    if pieces == "none":
        return []
    (bx, by), (upper, lower, end) = at, bones
    st = parts_mod.stations(lens, wid, taper)
    a = math.radians(angle)
    parts = []
    if pieces == "bend":
        p = parts_mod.piece(build, id, bx, by, angle, st, color)
        calls["bind"](layer=p, bone=upper, bone2=lower, soft=soft if soft is not None else max(0.6 * st[1][1], 6.0))
        parts.append(p)
    else:
        for bone_, s_, at_ in ((upper, st[:2], 0.0), (lower, st[1:], lens[0])):
            p = parts_mod.piece(build, f"{bone_.id}_part", bx, by, angle, s_, color, at=at_)
            calls["bind"](layer=p, bone=bone_)
            parts.append(p)
    if joint != "none":                     # made after the limb (on top: a ball); a round one goes under it
        jx, jy = bx + math.cos(a) * lens[0], by + math.sin(a) * lens[0]
        cap = parts_mod.joint_shape(build, f"{id}_joint", jx, jy, joint_size * max(st[1][1], st[2][1]), color)
        calls["bind"](layer=cap, bone=lower)
        if joint == "round":
            holder = build.holders[-1]["layers"]
            holder.remove(cap.node)
            holder.insert(holder.index(parts[0].node), cap.node)
        parts.append(cap)
    if end is not None:
        wx, wy = tip(lower.node)
        e = math.radians(ea)
        col = end_color or color
        if kind == "leg":
            p = build.layer("shape", f"{id}_foot", shape="rect", x=wx + math.cos(e) * lens[2] / 2, y=wy + math.sin(e) * lens[2] / 2,
                            w=lens[2] + wid[2], h=wid[2], radius=wid[2] / 2, rotation=ea, fill=col)
        else:
            p = build.layer("shape", f"{id}_hand", shape="ellipse", x=wx + math.cos(e) * lens[2] * 0.5,
                            y=wy + math.sin(e) * lens[2] * 0.5, w=wid[2], h=wid[2], fill=col)
        calls["bind"](layer=p, bone=end)
        parts.append(p)
    return parts
