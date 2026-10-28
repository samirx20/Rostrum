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
RELAX = {"arm": 35.0, "leg": 10.0}           # degrees the elbow / knee is bent at rest (relax=0: straight)
HANDS = ("mitten", "ball")
BODY_SHARE = {"arm": 0.26, "leg": 0.3}       # widths=None: the upper part this share of the body's width (the biggest
                                             # shape bound to the bones above), the rest from it (widths_from)
FOREARM, HAND, FOOT = 0.85, 1.05, 0.8        # the forearm / calf, the hand and the foot: these x the upper part
LENGTH_SHARE = 0.4                           # ... no body shape found: the upper part this share of the upper length
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


def make(build, rig, limbs: list, id, x=None, y=None, angle=90, lengths=(120, 110, 30), widths=None, parent=None,
         kind="arm", ik=None, bend=None, pieces="bend", color=None, end_color=None, end_angle=None, soft=None, relax=None,
         natural=True, taper=0.2, joint="round", joint_size=1.12, outline=True, outline_width=None, hand="mitten") -> Limb:
    """script limb(): see the guide and server.py's script tool description. Appends what the end-of-script pass needs
    (colour, outline, the natural bend, widths from the body) to `limbs`."""
    if kind not in LIMB_KINDS:
        raise ValueError(f'limb {id}: kind "{kind}" is not one of {", ".join(LIMB_KINDS)}')
    if pieces not in PIECES:
        raise ValueError(f'limb {id}: pieces "{pieces}" is not one of {", ".join(PIECES)}')
    if joint not in parts_mod.JOINTS:
        raise ValueError(f'limb {id}: joint "{joint}" is not one of {", ".join(parts_mod.JOINTS)}')
    if hand not in HANDS:
        raise ValueError(f'limb {id}: hand "{hand}" is not one of {", ".join(HANDS)}')
    if not 0 <= float(taper) < 1:
        raise ValueError(f"limb {id}: taper {taper} must be from 0 (even) up to below 1")
    lens = tuple(float(v) for v in lengths) + (0.0,) * (3 - len(lengths))
    if lens[0] <= 0 or lens[1] <= 0:
        raise ValueError(f"limb {id}: the first two lengths (upper, lower) must be above 0, not {lengths}")
    wid = widths_from(kind, LENGTH_SHARE * lens[0]) if widths is None else \
        tuple(float(v) for v in widths) + (widths[-1],) * (3 - len(widths))
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
    geom = dict(id=id, kind=kind, pieces=pieces, joint=joint, joint_size=joint_size, hand=hand, at=(bx, by), angle=angle,
                ea=ea, lens=lens, taper=float(taper), wrist=tip(lower.node) if end is not None else None,
                thumb=1 if math.sin(math.radians(ea)) * (mid - bx) >= 0 else -1)   # the thumb toward the body
    parts, binds = _parts(build, calls, geom, wid, (upper, lower, end), color, end_color, soft)
    out = (-1 if math.sin(math.radians(angle)) >= 0 else 1) * (1 if bx >= mid else -1)   # tip moves away from mid
    made = Limb(id, kind, upper, lower, end, chain, parts, out=int(out))
    limbs.append({"limb": made, "rig": rig, "relax": rlx if not has_ik else 0.0, "sign": sign,
                  "auto_color": auto_color and end_color is None, "natural": natural and not has_ik,
                  "outline": None if outline is True else outline, "outline_width": outline_width, "wid": wid,
                  "auto_width": widths is None, "geom": geom, "binds": binds, "soft": soft})
    return made


def widths_from(kind: str, upper: float) -> tuple[float, float, float]:
    """widths=None: (upper part, forearm or calf, hand or foot) from the upper part's width."""
    return upper, FOREARM * upper, (HAND if kind == "arm" else FOOT) * upper


def line_width(rec: dict) -> float:
    """The outline's width: outline_width=, else a tenth of the upper part's width (at least 2 px)."""
    return float(rec["outline_width"]) if rec["outline_width"] is not None else max(2.0, 0.1 * rec["wid"][0])


def _parts(build, calls, g, wid, bones, color, end_color, soft):
    """Make the shapes (limb_parts.shapes) and bind them: (parts, {part id: its bind})."""
    by_name = dict(zip(("upper", "lower", "end"), bones))
    parts, binds = [], {}
    for s in parts_mod.shapes(g, wid):
        p = build.layer(s["type"], s["id"], fill=(end_color or color) if s["bone"] == "end" else color, **s["fields"])
        two = {"bone2": by_name[s["bone2"]], "soft": soft if soft is not None else s["soft"]} if s["bone2"] else {}
        binds[s["id"]] = calls["bind"](layer=p, bone=by_name[s["bone"]], **two)
        if s["under"]:                      # a round joint goes under the limb
            holder = build.holders[-1]["layers"]
            holder.remove(p.node)
            holder.insert(holder.index(parts[0].node), p.node)
        parts.append(p)
    return parts, binds


def resize(rec: dict, wid) -> None:
    """Re-shape a made limb's parts to new widths (the end-of-script pass, widths=None): same ids, binds and order."""
    rec["wid"] = wid
    nodes = {p.node["id"]: p.node for p in rec["limb"].parts}
    for s in parts_mod.shapes(rec["geom"], wid):
        if s["id"] in nodes:
            nodes[s["id"]].update(s["fields"])
            if s["bone2"] and rec["soft"] is None:
                rec["binds"][s["id"]].node["soft"] = s["soft"]


def fit_widths(limbs: list) -> None:
    """The end-of-script pass for limbs made with widths=None: the upper part BODY_SHARE of the body's width (the biggest
    shape bound to the bones above it); a limb with none above it (legs on a bare hip) takes its rig's arms' body."""
    skip = {p.node["id"] for rec in limbs for p in rec["limb"].parts}
    found = {id(rec): body_width(rec["rig"], rec["limb"].upper.node["parent"], skip) for rec in limbs}
    for rec in limbs:
        w = found[id(rec)] or max((found[id(r)] for r in limbs if r["rig"] is rec["rig"]), default=0.0)
        if rec["auto_width"] and w:
            resize(rec, widths_from(rec["limb"].kind, BODY_SHARE[rec["limb"].kind] * w))


def body_width(rig: dict, bone_id: str, skip: set) -> float:
    """The width of the biggest layer bound to this bone or the nearest bone above it that has one (0: none)."""
    bones, layers, stack = {b["id"]: b for b in rig["bones"]}, {}, list(rig.get("layers", []))
    while stack:
        n = stack.pop()
        layers[n.get("id")] = n
        stack += n.get("layers", [])
    while bone_id:
        sizes = [(float(n.get("w", 0) or 0) * float(n.get("h", 0) or 0), float(n.get("w", 0) or 0))
                 for b in rig.get("binds", []) if b.get("bone") == bone_id
                 for n in [layers.get(b.get("layer"))] if n is not None and n["id"] not in skip]
        if sizes:
            return max(sizes)[1]
        bone_id = bones.get(bone_id, {}).get("parent")
    return 0.0
