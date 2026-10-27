"""The Pose tool's one door to what it uses from elsewhere (CL5 contract): the joint finder and the drag solve
(rostrum3d.pose_joints, rostrum3d.pose_ik), the operations agents call (ops_pose: pose.find_joints, pose.rest,
pose.hold, pose.move_joint; a drag's release keys Turn like pose.drag), and the light live request (`clay_pose`,
engine contract v1.18). Every call the screen makes into them is here, so a changed name or argument is one line.
No Qt.

Spaces: `local` / `to` / `rest` are in the clay's own space (the holds are kept as resting spots there); `to` of a
joint move is a world point; turns are degrees, {bone id: {"rx", "ry", "rz"}}, absolute (as the bone's Turn keys are).
"""
from __future__ import annotations

from contextlib import contextmanager

from rostrum3d import ops_pose

TURN = ("rx", "ry", "rz")


def _ik():
    from rostrum3d import pose_ik
    return pose_ik


def out_of_date(clay: dict, data: dict | None = None) -> bool:
    """The clay has no joints yet, or its shape changed since they were found (`data`: the document)."""
    if not clay.get("bones"):
        return True
    from rostrum3d import pose_joints
    return bool(pose_joints.out_of_date(clay, data))


def bone_at(clay: dict, local, t: float) -> str:
    """The bone a spot on the clay (as drawn at time t) belongs to: the nearest posed segment."""
    return _ik().bone_at(clay, list(local), t) or ""


def solve(clay: dict, bone: str, local, to, holds: list[str], t: float) -> dict:
    """The turns that bring the grabbed spot (`local`, on `bone`, as drawn at t) to `to`, from the clay as given (the
    press-time clay: each move solves from the same start, so the release keys exactly what the last move showed)."""
    out = _ik().solve(clay, bone, list(local), list(to), holds=list(holds), t=t)
    turns = out.get("turns", out) if isinstance(out, dict) else out
    return {b: {k: float(v[k]) for k in TURN} if isinstance(v, dict) else dict(zip(TURN, map(float, v)))
            for b, v in turns.items()}


def chain_pose(clay: dict, turns: dict, t: float) -> list:
    """The `clay_pose` payload: one 12-number bone move per bone, the clay as at t with the bones in `turns` turned so."""
    return _ik().chain_pose(clay, turns, t)


def held(clay: dict) -> list[str]:
    """The bones under the clay's holds."""
    return list(_ik().held_bones(clay))


def holds_of(clay: dict) -> list[dict]:
    """The clay's holds, each {"at": its resting spot, "bone": the bone under it at rest}."""
    spots = [list(h) for h in clay.get("holds") or []]
    if not spots or not clay.get("bones"):
        return []
    r = _ik().rig(clay, 0.0)
    return [{"at": h, "bone": r.ids[r.bone_at(h, rest=True)]} for h in spots]


def send_pose(link, item: str, pose: list, then) -> None:
    """A pose drag's move, light: the clay drawn with these bone moves until the next scene."""
    own = getattr(link, "clay_pose", None)
    if own is not None:
        return own(item, pose, then)
    link.post({"clay_pose": {"item": item, "pose": pose}}, then)


# --- the document's calls (each list one undo step where the screen applies it)
def key_calls(turns: dict, t: float, clay: dict | None = None) -> list[dict]:
    """A drag's release: what pose.drag keys (pose_ik.drag_keys): the Turn of every bone that moved at t, and a bone
    keyed for the first time keeps its old turn at the clay's other key times."""
    keys = _ik().drag_keys(clay, turns, t) if clay is not None else [(b, k, t, v[k]) for b, v in turns.items() for k in TURN]
    return [{"op": "key.add", "target": [b], "args": {"prop": k, "v": round(v, 6), "t": at}} for b, k, at, v in keys]


CELLS = 48                       # the joint finder's grid: cells along the clay's longest side (pose.find_joints' default)


@contextmanager
def grid_given(grid: dict):
    """pose.find_joints run here reads this grid (fetched from the window's view beforehand), not the engine."""
    old = ops_pose._GRID
    ops_pose.use_grid(lambda doc, id_, cells: grid)
    try:
        yield
    finally:
        ops_pose._GRID = old


def find_calls(item: str, names: str | None = None) -> list[dict]:
    return [{"op": "pose.find_joints", "target": [item], "args": {"names": names} if names else {}}]


def rest_calls(item: str, at: float | None = None) -> list[dict]:
    return [{"op": "pose.rest", "target": [item], "args": {} if at is None else {"at": at}}]


def hold_calls(item: str, rest=None, bone: str = "", off: bool = False) -> list[dict]:
    """A hold at a resting spot, or (off) the hold nearest it / every hold on `bone`."""
    args = {"bone": bone} if bone else {"spot": [round(x, 6) for x in rest], "space": "rest"}
    return [{"op": "pose.hold", "target": [item], "args": {**args, **({"off": True} if off else {})}}]


def move_joint_calls(item: str, joint: str, to) -> list[dict]:
    return [{"op": "pose.move_joint", "target": [item], "args": {"joint": joint, "to": [round(x, 6) for x in to]}}]


def names_calls(item: str, names: str) -> list[dict]:
    """Joint names Plain / Humanoid: only the names change (bones, ids and keys stay)."""
    return [{"op": "pose.names", "target": [item], "args": {"names": names}}]
