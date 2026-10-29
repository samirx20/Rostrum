"""Posing a clay figure from a script (script.py's clay.pose): several parts at one time, each to a world point or an
offset from where it is at rest, solved by the drag solve (pose_ik) and written as keys at that time.

- `buddy.pose(0.5, **{"picture-right hand": {"up": 0.1}, "head": (0, 0.3, 0.05)}, holds=)`: one pose per call; chain
  calls for a motion. A target is a world point (x, y, z), or {"up": m, "out": m, "forward": m}: metres from where the
  part's end is at rest, along the figure's own up, away from its middle (a left or right part only) and the way it
  faces (+Z at rest); negative goes down / in / back. Names: pose_names.py.
- `buddy.pose("hand.R", {t: (x, y, z), …})`: the older form, one part at several times (world points or offsets).
- Notes for the reply (Build.notes): a target out of reach (how far it is, the reach, it stops short) and a target on
  the far side of the body (did you mean the other hand?). Not errors: the pose is still made.
"""
from __future__ import annotations

from . import aim, pose_ik, pose_names
from .resolve import Frames
from .script_figure import _put, _rig, _scene, _times

AXES = ("up", "out", "forward")
ROOT = {"arm": "shoulder", "forearm": "shoulder", "hand": "shoulder", "leg": "hip", "shin": "hip", "foot": "hip", "toe": "hip"}


def pose_at(b, node: dict, t, parts: dict, holds=None, ease: str = "smooth"):
    """One pose at time t (seconds): each named part's end to its target, in the order given."""
    owner = f"{node['id']}.pose"
    if not isinstance(t, (int, float)):
        raise ValueError(f'{owner}: the first argument is the time in seconds (or a part name with {{seconds: target}}), '
                         f'e.g. .pose(0.5, **{{"right hand": {{"up": 0.2, "out": -0.1}}}})')
    if not parts:
        raise ValueError(f'{owner}({t:g}): name the parts and where they go, e.g. .pose({t:g}, **{{"head": {{"forward": 0.02}}}})')
    t, f = float(t), round(float(t) * 1000)
    world = Frames(b.root, range(f, f + 1), 1000.0).world(node["id"], f)
    scale = abs(aim.det(world[0])) ** (1 / 3) or 1.0
    for name, target in parts.items():
        r = _rig(b, node, t)
        g = pose_names.resolve(name, r, owner, _seen(b, r, world, f))
        local = _target(owner, name, r, g, target, world)
        out = pose_ik.solve_rig(r, g, [0.0, r.length[g], 0.0], local, r.held(holds if holds is not None else node.get("holds") or []))
        _put(node, out["turns"], t, ease)
        b.notes.extend(f"{node['id']} at {t:g} s: {n}" for n in _notes(b, r, g, name, local, out["miss"], scale, world, f))


def pose(b, node: dict, part: str, keys, holds=None, ease: str = "smooth"):
    """The older form: one part, {seconds: target}."""
    for t, to in _times(f"{node['id']}.pose", keys):
        pose_at(b, node, t, {part: to}, holds, ease)


def _seen(b, r, clay_world, f):
    """seen(part) -> its .L / .R joints from the picture's left to right through the first shot's camera; None with
    no camera."""
    data = _scene(b)
    cam = next((s.get("camera") for s in data.get("shots", []) if s.get("camera")), None)
    if cam is None:
        return None
    frames = Frames(data, range(f, f + 1), 1000.0)
    try:
        cam_world = frames.world(cam, f)
    except KeyError:
        return None
    posed = r.frames()

    def seen(part: str) -> list[str]:
        ends = {}
        for s in "LR":
            try:
                n = r.find(f"{part}.{s}")
            except ValueError:
                continue
            ends[f"{part}.{s}"] = aim.point(clay_world, pose_ik._at(posed[n], [0.0, r.length[n], 0.0]))
        return pose_names.picture_left(cam_world, ends)
    return seen


def _side(joint: str) -> int:
    return 1 if joint.endswith(".L") else -1 if joint.endswith(".R") else 0       # .L is on the clay's +X


def _target(owner: str, name: str, r, g: int, target, world) -> list[float]:
    """The target in the clay's own space."""
    to_local = aim.invert(world)
    if isinstance(target, dict):
        bad = [k for k in target if k not in AXES]
        side = _side(r.joint[g])
        if bad or ("out" in target and not side):
            why = f'"{bad[0]}" is not one of up / out / forward' if bad else f'{r.joint[g]} is in the middle, it has no "out"'
            raise ValueError(f'{owner}: {name} target: {why}. A target is a world point (x, y, z), or {{"up": m, "out": m, '
                             '"forward": m}: metres from where the part is at rest, along the figure\'s own up, away from '
                             'its middle, and the way it faces; negative goes down / in / back')
        rest_end = aim.point(world, pose_ik._at(r.rest[g], [0.0, r.length[g], 0.0]))
        here = aim.point(world, [0.0, 0.0, 0.0])
        out = list(rest_end)
        for k, axis in (("up", (0, 1, 0)), ("out", (side, 0, 0)), ("forward", (0, 0, 1))):
            d = [a - h for a, h in zip(aim.point(world, list(axis)), here)]
            n = sum(x * x for x in d) ** 0.5 or 1.0
            out = [o + float(target.get(k, 0.0)) * x / n for o, x in zip(out, d)]
        return aim.point(to_local, out)
    try:
        p = [float(c) for c in target]
        assert len(p) == 3
    except (TypeError, ValueError, AssertionError):
        raise ValueError(f'{owner}: {name} target {target!r}: a world point (x, y, z), or {{"up": m, "out": m, "forward": m}} '
                         "from where the part is at rest") from None
    return aim.point(to_local, p)


def _m(x: float) -> str:
    return f"{x:.2f} m" if x >= 0.1 else f"{x:.3f} m"


def _notes(b, r, g: int, name: str, local, miss: float, scale: float, world, f) -> list[str]:
    out, joint = [], r.joint[g] or r.ids[g]
    root, reach = g, 0.0                          # the limb's own chain: from its end up to where it joins the body
    while root >= 0 and not r.trunk[root]:
        reach += r.length[root]
        if r.parent[root] < 0 or r.trunk[r.parent[root]]:
            break
        root = r.parent[root]
    if miss * scale > max(0.005, 0.05 * reach * scale):
        if root >= 0 and not r.trunk[root]:
            at = r.frames()[root][1]
            d = sum((a - c) ** 2 for a, c in zip(local, at)) ** 0.5
            where = ROOT.get(joint.split(".")[0], "joint it hangs from")
            out.append(f"{name} target is {_m(d * scale)} from the {where}, its reach is {_m(reach * scale)}; "
                       f"it stops short ({_m(miss * scale)} away)")
        else:
            out.append(f"{name} target is out of reach; it stops short ({_m(miss * scale)} away)")
    side = _side(joint)
    middle = r.head[0][0]
    if side and side * (local[0] - middle) < -max(0.1 * reach, 1e-3):
        part = pose_names.words(name)[0].split(".")[0]
        other = f"{part}.{'R' if side > 0 else 'L'}"
        seen = _seen(b, r, world, f)
        pic = ""
        if seen is not None:
            order = seen(part)
            if other in order and len(order) == 2:
                pic = f" / picture-{'left' if order[0] == other else 'right'} {part}"
        out.append(f"{name}'s target is on the figure's {'right' if side > 0 else 'left'} side, past its middle; "
                   f"did you mean {other}{pic}?")
    return out
