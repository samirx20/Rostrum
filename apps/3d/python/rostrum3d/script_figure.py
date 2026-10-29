"""A figure as ONE clay in a script (script.py): its start as a ball or a capsule (clay.add's at / radius, + to), resting
on the ground when no height was given, and posed from the script with keys over time.

- `clay("buddy", radius=0.08)`: a ball resting on the ground: the clay's origin is on the ground under it (the
  ball's middle at (0, radius, 0) in its own space), so the clay's own space is the scene's and every .lump / .stroke
  position is a height above the ground. `at=(x, y, z)` places the ball's middle there instead (the clay's origin
  there too; a height given: kept); `to=` makes the start a capsule from `at` to `to`. Without at / y / draw / spin, the clay is built where the script's numbers put it,
  and when the script ends it moves up or down so its lowest point (at rest, every joined piece) is on the ground's
  top, everything attached to it moving with it: a figure never floats, and no part is left behind.
- `buddy.pose(t, **{"hand.R": target, …})`: script_pose.py (names: pose_names.py); `buddy.bend("head",
  {t: (x, y, z) degrees, …})`: turn a joint about the clay's own X / Y / Z (as it faces +Z, at rest) by that much from
  its rest. The joints are found once, from the clay's shape, with the engine (pose.find_joints' finder), the first
  time the clay is posed; so pose after the last lump.
"""
from __future__ import annotations

import copy

from rostrum_core.keys import key_id

from . import aim, build, clay_steps, ops_pose, pose_ik, pose_joints as PJ, script_ground

CELLS = 48
LISTS = ("items", "materials", "shots")


# --- the start
def start(values: dict) -> tuple[dict, dict | None, bool]:
    """(the clay's own fields, its first step or None, whether it rests on the ground) from clay(...)'s arguments."""
    at, to, radius = values.pop("at", None), values.pop("to", None), values.pop("radius", None)
    shape = values.pop("shape", None)
    if shape not in (None, "sphere", "ball", "capsule"):
        raise ValueError(f'clay shape "{shape}": a clay starts as a sphere (radius=), a capsule (to=), or draw= / spin=')
    if shape == "capsule" and to is None:
        raise ValueError('a capsule clay needs to=(x, y, z), its other end')
    grounded = at is None and "y" not in values
    if at is None and to is None and radius is None:
        return values, None, grounded                   # an empty clay: its steps come from .lump / .draw …
    r = float(radius or clay_steps.RADIUS)
    if at is None and to is None:                      # on the ground: the clay's origin on the ground under the
        piece = {"at": [0.0, r, 0.0], "radius": r}     # ball, so its own space is the scene's (y = height)
        values.update({k: float(values.get(k, 0.0)) for k in "xyz"})
    else:
        at = [float(c) for c in at] if at is not None else [float(values.get(k, 0.0)) for k in "xyz"]
        values.update(x=at[0], y=at[1], z=at[2])
        piece = {"at": [0.0, 0.0, 0.0], "radius": r}
    if to is not None:
        piece["to"] = [round(float(b) - a, 6) for a, b in zip(at, to)]
    first = clay_steps.piece_values({"symmetry": values.get("symmetry") or "x"}, piece,
                                    "capsule" if to is not None else "sphere")
    values.setdefault("brushSize", round(max(r / 4, 0.0005), 4))
    return values, first, grounded


# --- resting on the ground: the one ground rule (script_ground.py)
ground_top, rest_on_ground, settle = script_ground.ground_top, script_ground.rest_on_ground, script_ground.settle_clay


# --- joints
def _scene(b) -> dict:
    """The open document with what the script made so far over it (top level, by id): what the engine builds."""
    doc = b.doc.data if b.doc is not None else {lst: [] for lst in LISTS}
    data = {k: v if k in LISTS else _copy(v) for k, v in doc.items()}
    for lst in LISTS:                                   # only the document's nodes the script doesn't replace are copied
        mine = {n["id"]: n for n in b.root.get(lst, [])}
        data[lst] = [mine.pop(n["id"]) if n["id"] in mine else _copy(n) for n in data.get(lst, [])] \
            + list(mine.values())
    return data


def _copy(v):
    """copy.deepcopy for the document's plain data (dicts, lists, text, numbers), ~5× faster; anything else deep-copied."""
    if type(v) is dict:
        return {k: _copy(x) for k, x in v.items()}
    if type(v) is list:
        return [_copy(x) for x in v]
    return v if v is None or type(v) in (str, int, float, bool) else copy.deepcopy(v)


def find_joints(b, node: dict):
    """pose.find_joints for a clay the script is making: the engine measures its shape, the finder names the joints
    (body, chest, head, arm.L / forearm.L / hand.L, leg / foot …), and they are written as its bones."""
    if ops_pose._GRID is None:
        raise ValueError(f"{node['id']}: posing needs the engine to find the joints; run the script with run_script")
    if not node.get("steps"):
        raise ValueError(f"{node['id']}: has no shape yet; make it (radius=, .lump, .draw) before posing")
    data = _scene(b)
    if not data.get("shots"):
        raise ValueError(f"{node['id']}: the engine builds the scene through a shot; make the shot first")
    every = all(st.get("symmetry", "x") == "x" for st in node["steps"] if not st.get("hidden"))
    grid = ops_pose._GRID(data, node["id"], CELLS)
    if (more := PJ.finer_cells(node, grid, CELLS)) > CELLS:
        grid = ops_pose._GRID(data, node["id"], more)
    found, parts = PJ.find_parts(grid, mirror=True if every else None)
    made: dict[str, dict] = {}
    node["bones"] = []
    for j, values in zip(found, PJ.rest_bones(found)):
        id_ = b.new_id(PJ.bone_id(node["id"], j["joint"]), loose=True)
        bone = build.make("bone", id_, {"name": j["joint"], "joint": j["joint"], **values}, f"script › {node['id']}")
        (made[j["parent"]]["bones"] if j["parent"] else node["bones"]).append(bone)
        made[j["joint"]] = bone
    node.update(jointNames="plain", jointsKey=PJ.steps_key(node, data), jointParts=PJ.pack_parts(parts))


def _rig(b, node: dict, t: float) -> pose_ik.Rig:
    if not node.get("bones"):
        find_joints(b, node)
    return pose_ik.Rig(node, t)


def _part(r: pose_ik.Rig, owner: str, name: str) -> int:
    try:
        return r.find(name)
    except ValueError as e:
        raise ValueError(f"{owner}: {e}") from None


def _put(node: dict, turns: dict, t: float, ease: str):
    bones = {bone["id"]: bone for bone, _ in pose_ik.skin.bones_of(node)}
    for id_, p, at, v in pose_ik.drag_keys(node, turns, t, fill=False):
        k = {"id": key_id(id_, p, at), "type": "key", "prop": p, "t": float(at), "v": round(v, 6) + 0.0,
             "ease": ease}
        bones[id_]["keys"] = [o for o in bones[id_]["keys"] if o["id"] != k["id"]] + [k]


def _times(owner: str, keys) -> list:
    if not isinstance(keys, dict) or not keys:
        raise ValueError(f"{owner}: keys are {{seconds: value}}, e.g. {{0: …, 1.5: …}}")
    return sorted((float(t), v) for t, v in keys.items())


def bend(b, node: dict, joint: str, keys, ease: str = "smooth"):
    """Turn one joint by (x, y, z) degrees about the clay's own axes (as at rest) from its rest, at each time."""
    for t, by in _times(f"{node['id']}.bend", keys):
        r = _rig(b, node, t)
        n = _part(r, f"{node['id']}.bend", joint)
        p = r.parent[n]
        lin = r.rest[p][0] if p >= 0 else aim.IDENTITY[0]
        turn = aim._mul(pose_ik._t(lin), aim._mul(pose_ik._rot(*map(float, by)), aim._mul(lin, pose_ik._rot(*r.rest_turn[n]))))
        e = pose_ik._near(aim.euler(turn), r.turn[n])
        _put(node, {r.ids[n]: dict(zip(pose_ik.TURN, e))}, t, ease)
