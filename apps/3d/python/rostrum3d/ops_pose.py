"""Pose by dragging (SPEC §4, CL5): the operations. A clay's joints are found from its shape (`pose.find_joints`,
pose_joints.py) and written as its `bones`, exactly like a mesh's chain (skin.py: posed only by keys on each bone's
Turn, absolute turns, unkeyed = rest); `pose.drag` bends the chain from a grabbed part back towards the body
(pose_ik.py) and keys the Turn of every bone that moved; `pose.hold` keeps spots still; `pose.rest` takes the pose
off; `pose.move_joint` places a joint by hand (kept when the joints are found again). Each is one undo step.

Bone ids are `<clay>_<part>` (body, arm_L, foot_R …), so keys survive finding the joints again; finding them again
keeps every bend (each bone's turn relative to its rest) and every joint a person or agent placed.
`pose.find_joints` needs the clay's shape from the core (its `clay_grid`): the app and the MCP server hand their
engine over with ops_mesh.use_engine, which hands it on here; without one it fails loudly.
"""
from __future__ import annotations

import math

from rostrum_core import Param
from rostrum_core.errors import codes
from rostrum_core.keys import keys_of, track_value

from . import aim, build, compile as C, pose_ik, pose_joints as PJ, resolve
from .kind import REGISTRY as R
from .ops_keys import put_key

TURN = pose_ik.TURN
_GRID = None              # (doc, clay id, cells) -> the core's clay_grid reply


def use_engine(engine, folder=None):
    """Let pose.find_joints ask this engine for a clay's grid (through the document's first shot's scene)."""
    global _GRID

    def grid(doc: dict, id_: str, cells: int) -> dict:
        shots = doc.get("shots") or []
        if not shots:
            raise ValueError("the document has no shot yet, so the engine can't build the scene (shot.add first)")
        engine.ensure_scene(_with_held_skins(C.describe(doc, shots[0]["id"], folder), getattr(engine, "_held", None)))
        return engine.clay_grid(id_, cells)
    _GRID = grid if engine is not None else None


def _clays(items: list) -> dict:
    out = {}
    for n in items:
        if n.get("type") == "clay":
            out[n["id"]] = n
        out.update(_clays(n.get("children", [])))
    return out


def _with_held_skins(scene: dict, held: dict | None) -> dict:
    """The scene for a clay's grid, keeping the bones the engine already holds on a clay whose shape is unchanged.
    A script being run has taken its clay's bones off to find them again; sent like that, the engine would put the
    clay at rest and weigh every block again when the look's scene brings the same bones back (seconds on a figure).
    The grid measures the shape at rest, so the bones it holds change nothing in it. A changed shape goes without."""
    if not held:
        return scene
    before = _clays(held.get("items", []))
    for id_, n in _clays(scene.get("items", [])).items():
        old = before.get(id_)
        if ("skin" not in n and old and "skin" in old and old.get("steps") == n.get("steps")
                and old["props"].get("detail") == n["props"].get("detail")):
            n["skin"] = old["skin"]
    return scene


def use_grid(fn):
    """Tests: any (doc, clay id, cells) -> clay_grid-shaped dict."""
    global _GRID
    _GRID = fn


NAMES = Param.choice("names", ["plain", "humanoid"], label="Joint names", importance="secondary",
                     help="plain: body, chest, arm.L, forearm.L, foot.R …; humanoid: Hips, Spine, LeftUpperArm, "
                          "LeftLowerArm, RightFoot … (Unity's Humanoid / VRM). Default: the clay's Joint names")
CELLS = Param.number("cells", label="Grid", min=8, max=128, integer=True, default=48, importance="deep",
                     help="How finely the shape is sampled along its longest side (more finds thin limbs, slower)")
POINT = lambda name, label, help, required=True: Param.list(  # noqa: E731
    name, "number", label=label, min=-1e5, max=1e5, min_items=3, max_items=3, required=required, help=help)
GRAB = Param.list("grab", "number", label="Grab", min=-1e5, max=1e5, min_items=0, max_items=3, importance="secondary",
                  help="A world point on the clay to grab (where it stands at `at`); or give `part` instead")
PART = Param.text("part", label="Part", help='The part to grab by name: a joint ("hand.R", "foot.L", "head"), its '
                  'Humanoid name ("RightHand") or a bone id; the grabbed spot is the end of that bone')
TO = POINT("to", "To", "Where the grabbed spot goes: a world point")
HOLDS = Param.list("holds", "text", label="Holds", importance="secondary", default=None, nullable=True,
                   help="Joints that stay put for this drag (names or bone ids); default: the clay's own holds "
                        "(pose.hold). [] holds nothing")
AT = Param.number("at", label="At", min=0, max=36000, step=0.001, unit="s", default=0.0,
                  help="The time to pose at, seconds (the Turn keys go there)")
SPOT = POINT("spot", "Spot", "A world point on the clay (where it stands at `at`)", required=False)
SPACE = Param.choice("space", ["world", "rest"], label="Spot in", default="world", importance="deep",
                     help="world: a scene position at time `at` (default). rest: the clay's own space at rest (the "
                          "core's pick gives it as `rest`)")
BONE = Param.text("bone", label="Joint", help="A joint name or bone id (holds the middle of that bone)")
OFF = Param.toggle("off", label="Let go", help="Remove the hold at that spot (or every hold on that joint)")
JOINT = Param.text("joint", label="Joint", required=True, help='A joint name ("forearm.L") or bone id')
WHERE = POINT("to", "To", "Where the joint's head goes: a world point, at rest (where the clay stands at time 0)")


# --- spaces
def _world(doc: dict, id_: str, t: float = 0.0):
    if not t:
        return resolve.world_at_start(doc, id_)
    f = round(t * 1000)
    return resolve.Frames(doc, range(f, f + 1), 1000.0).world(id_, f)


def _to_clay(ctx, id_, p, t=0.0):
    return aim.point(aim.invert(_world(ctx.doc, id_, t)), [float(x) for x in p])


def _to_world(ctx, id_, p, t=0.0):
    return [round(x, 6) for x in aim.point(_world(ctx.doc, id_, t), p)]


def _one_clay(ctx, targets) -> dict:
    if len(targets) != 1:
        ctx.fail(codes.BAD_ARGUMENT, "targets", f"name {len(targets)} items; pose one clay at a time")
    return ctx.item(targets[0])


def _rig(ctx, clay, t=0.0) -> pose_ik.Rig:
    if not clay.get("bones"):
        ctx.fail(codes.BAD_ARGUMENT, clay["id"], "has no joints yet", hint="pose.find_joints finds them from its shape.")
    return pose_ik.Rig(clay, t)


def _find(ctx, r, name) -> int:
    try:
        return r.find(name)
    except ValueError:
        ctx.fail(codes.BAD_ARGUMENT, f'joint "{name}"', "is not a joint of this clay",
                 [j or i for j, i in zip(r.joint, r.ids)])


# --- writing joints as bones, keeping bends
def _bends(clay: dict) -> dict:
    """Each bone's Turn keys as bends: {bone id: [(t, bend 3×3, the key's ease), …]}, bend = rest⁻¹ · turn."""
    out = {}
    for bone in _all_bones(clay):
        times = sorted({k["t"] for p in TURN for k in keys_of(bone, p)})
        if not times:
            continue
        rest = pose_ik._rot(*(float(bone.get(p, 0.0)) for p in TURN))
        rows = []
        for t in times:
            turn = [float(track_value(keys_of(bone, p), t)) if keys_of(bone, p) else float(bone.get(p, 0.0))
                    for p in TURN]
            ease = next((k.get("ease", "smooth") for p in TURN for k in keys_of(bone, p) if k["t"] == t), "smooth")
            rows.append((t, aim._mul(pose_ik._t(rest), pose_ik._rot(*turn)), ease))
        out[bone["id"]] = rows
    return out


def _all_bones(item: dict) -> list[dict]:
    return [b for b, _ in pose_ik.skin.bones_of(item)]


def _write(ctx, clay: dict, joints: list[dict], names: str):
    """Replace the clay's bones with these joints (clay space, parents first), each bend kept as a bend."""
    bends = _bends(clay)
    for old in list(clay.get("bones", [])):
        ctx.remove(old["id"])
    ids = {j["joint"]: PJ.bone_id(clay["id"], j["joint"]) for j in joints}
    for j, values in zip(joints, PJ.rest_bones(joints)):
        id_ = ids[j["joint"]]
        bone = build.make("bone", id_, {"name": PJ.shown_name(j["joint"], names), "joint": j["joint"],
                                        "placed": bool(j.get("placed")), **values}, ctx.where)
        rest, prev = pose_ik._rot(values["rx"], values["ry"], values["rz"]), (values["rx"], values["ry"], values["rz"])
        for t, bend, ease in bends.get(id_, ()):
            e = pose_ik._near(aim.euler(aim._mul(rest, bend)), prev)
            prev = e
            for p, v in zip(TURN, e):
                bone["keys"].append({"id": f"{id_}_{p}_k{len(bone['keys'])}", "type": "key", "prop": p, "t": t,
                                     "v": round(v, 6) + 0.0, "ease": ease})
        _key_ids(bone)
        ctx.insert(ids[j["parent"]] if j["parent"] else clay["id"], "bones", bone)
    return ids


def _key_ids(bone: dict):
    """Keys get the usual ids (owner, field, time) and the usual order (by field, then time)."""
    from rostrum_core.keys import key_id
    bone["keys"].sort(key=lambda k: (k["prop"], k["t"]))
    for k in bone["keys"]:
        k["id"] = key_id(bone["id"], k["prop"], k["t"])


def _reply_joints(ctx, clay_id: str, ids: dict) -> list[dict]:
    clay = ctx.item(clay_id)
    world = _world(ctx.doc, clay_id)
    return [{"id": j["id"], "joint": j["joint"], "head": [round(x, 6) for x in aim.point(world, j["head"])],
             "tail": [round(x, 6) for x in aim.point(world, j["tail"])], "parent": j["parent"]}
            for j in PJ.joints_of(clay)]


# --- the operations
@R.operation("pose.find_joints", "Find a clay's joints from its shape, so it can be posed by dragging (pose.drag): "
             "the thickest part is the body (bone `body`, the root), and every limb (a branch to a tip) gets a joint "
             "where it meets the body, where it bends most, and a middle one when it is long (a straight arm still "
             "bends at the shoulder AND the elbow). Names: body, chest (where the arms join), head; arm / forearm / "
             "hand, leg / shin / foot, a short limb at the bottom foot, tail, part3 …; limbs on the clay's +X side are "
             ".L (the character's left when it faces +Z), on −X .R. Bone ids are <clay>_<part> (clay_arm_L). Finding "
             "them again after the shape changed keeps every joint placed by hand (pose.move_joint) and every bend "
             "(keys). Each piece (the body, each limb) bends only with its own joints, shared smoothly round the joint where it "
             "meets the body (a raised arm stretches the shoulder, never pulls the side or hip). Reply: the joints, "
             "each {id, joint, head, tail (world), parent}, and `dropped`: the old joints the new shape no longer has. Look at them with look_frame "
             "before posing; move a wrong one with pose.move_joint.",
             target="clay", label="Find joints", params=[NAMES, CELLS])
def pose_find_joints(ctx, targets, args):
    clay = _one_clay(ctx, targets)
    if _GRID is None:
        ctx.fail(codes.BAD_ARGUMENT, clay["id"], "can't be measured without the engine",
                 hint="Run it in the app or through the MCP server (they hand their engine over: ops_mesh.use_engine).")
    if not clay.get("steps"):
        ctx.fail(codes.BAD_ARGUMENT, clay["id"], "has no shape yet", hint="clay.draw / clay.shape make some first.")
    try:
        every = all(st.get("symmetry", "x") == "x" for st in clay["steps"] if not st.get("hidden"))   # built mirrored
        asked = int(args.get("cells") or 48)
        grid = _GRID(ctx.doc, clay["id"], asked)
        if not args.get("cells") and (more := PJ.finer_cells(clay, grid, asked)) > asked:    # a thin part: look finer
            grid = _GRID(ctx.doc, clay["id"], more)
        found, parts = PJ.find_parts(grid, mirror=True if every else None)
    except (ValueError, KeyError) as e:
        ctx.fail(codes.BAD_ARGUMENT, clay["id"], f"no joints found: {e}")
    names = args.get("names") or clay.get("jointNames", "plain")
    old = PJ.joints_of(clay) if clay.get("bones") else []
    ids = _write(ctx, clay, PJ.merge(found, old), names)
    ctx.set(clay["id"], "jointNames", names)
    ctx.set(clay["id"], "jointsKey", PJ.steps_key(clay, ctx.doc))
    ctx.set(clay["id"], "jointParts", PJ.pack_parts(parts))
    now = {j["joint"] for j in found} | {o["joint"] for o in old if o.get("placed")}
    return {"joints": _reply_joints(ctx, clay["id"], ids),
            "dropped": sorted(o["joint"] for o in old if o["joint"] not in now)}


@R.operation("pose.names", "Show a clay's joints with plain names (body, arm.L, foot.R …) or Humanoid ones (Hips, "
             "LeftUpperArm, RightFoot …, as Unity's Humanoid and VRM name them). Only the names change: the bones, "
             "their ids and their keys stay.", target="clay", label="Joint names",
             params=[Param.choice("names", ["plain", "humanoid"], label="Joint names", required=True, help=NAMES.help)])
def pose_names(ctx, targets, args):
    for t in targets:
        clay = ctx.item(t)
        for bone in _all_bones(clay):
            if bone.get("joint"):
                ctx.set(bone["id"], "name", PJ.shown_name(bone["joint"], args["names"]))
        ctx.set(t, "jointNames", args["names"])


@R.operation("pose.drag", "Pose a clay by dragging a part: the chain from the grabbed bone back towards the body "
             "bends so the grabbed spot goes to `to` (each joint turning as little as it can; the body's own bones "
             "turn less than limbs). Grab by `part` (\"hand.R\": the end of that bone) or by `grab`, a world point "
             "on the clay. Held joints (`holds`, default the clay's holds from pose.hold) stay put, and so does every "
             "bone that carries one (e.g. hold both feet: the body stays, only the arm bends); with no holds the "
             "root (body) doesn't turn. Keys the Turn of every bone that moved at `at` (seconds). Reply: the moved "
             "joints with their turns, and `miss`: how far (m) the spot ended from `to` (more than 0 = out of reach).",
             target="clay", label="Pose by dragging", params=[PART, GRAB, TO, HOLDS, AT])
def pose_drag(ctx, targets, args):
    clay = _one_clay(ctx, targets)
    t = float(args.get("at", 0.0))
    r = _rig(ctx, clay, t)
    if args.get("part"):
        g = _find(ctx, r, args["part"])
        spot = [0.0, r.length[g], 0.0]
    elif args.get("grab"):
        p = _to_clay(ctx, clay["id"], args["grab"], t)
        frames = r.frames()
        g = r.bone_at(p)
        spot = aim.point(aim.invert(frames[g]), p)
    else:
        ctx.fail(codes.BAD_ARGUMENT, "part", "is required (or grab, a world point on the clay)",
                 hint='e.g. part="hand.R"')
    holds = args["holds"] if args.get("holds") is not None else clay.get("holds") or []
    try:
        held = r.held(holds)
    except ValueError as e:
        ctx.fail(codes.BAD_ARGUMENT, "holds", str(e))
    out = pose_ik.solve_rig(r, g, spot, _to_clay(ctx, clay["id"], args["to"], t), held)
    for id_, p, at, v in pose_ik.drag_keys(clay, out["turns"], t):
        put_key(ctx, id_, p, at, {"v": v})
    joint = {i: j or i for i, j in zip(r.ids, r.joint)}
    scale = _scale(ctx, clay["id"], t)
    return {"moved": [{"id": i, "joint": joint[i], "turn": [out["turns"][i][p] for p in TURN]} for i in out["moved"]],
            "grabbed": joint[r.ids[g]], "miss": round(out["miss"] * scale, 6),
            "held": sorted(joint[r.ids[n]] for n in held),
            **({} if out["moved"] else {"note": "nothing could turn: the grabbed joint is held or carries a hold"})}


def _scale(ctx, id_, t) -> float:
    """How many world metres one clay-space metre is (its scale), for distances in replies."""
    lin = _world(ctx.doc, id_, t)[0]
    return abs(aim.det(lin)) ** (1 / 3)


@R.operation("pose.hold", "Hold a spot of a posed clay so it stays put while other parts are dragged (a foot on the "
             "ground): the bone under it, and every bone that carries it, won't turn in pose.drag. Give a `spot` "
             "(a world point on the clay) or a `bone` (joint name); off removes the hold there (or every hold on that "
             "joint). Holds are kept on the clay (its `holds`, resting spots) and shown as rings while Pose is on.",
             target="clay", label="Hold", params=[SPOT, BONE, OFF, AT, SPACE])
def pose_hold(ctx, targets, args):
    clay = _one_clay(ctx, targets)
    t = float(args.get("at", 0.0))
    r = _rig(ctx, clay, t)
    holds = [list(h) for h in clay.get("holds") or []]
    if args.get("bone"):
        n = _find(ctx, r, args["bone"])
        seg = pose_ik.skin.segment(r.rest[n], r.bones[n])
        rest = [(a + b) / 2 for a, b in zip(seg[:3], seg[3:])]
    elif args.get("spot"):
        rest = [float(x) for x in args["spot"]] if args.get("space") == "rest" else \
            _carry_back(r, _to_clay(ctx, clay["id"], args["spot"], t))
        n = r.bone_at(rest, rest=True)
    else:
        ctx.fail(codes.BAD_ARGUMENT, "spot", "is required (or bone, a joint name)")
    if args.get("off"):
        near = [h for h in holds if r.bone_at(h, rest=True) == n] if args.get("bone") else \
            sorted(holds, key=lambda h: math.dist(h, rest))[:1]
        if not near:
            ctx.fail(codes.BAD_ARGUMENT, clay["id"], "has no hold there", hint=f"It holds {len(holds)} spots.")
        holds = [h for h in holds if h not in near]
    else:
        holds.append([round(x, 6) + 0.0 for x in rest])
    ctx.set(clay["id"], "holds", holds or None)                 # none: null (a points list is never empty)
    return {"holds": len(holds), "joint": r.joint[n] or r.ids[n]}


def _carry_back(r: pose_ik.Rig, p) -> list[float]:
    """A spot on the clay as posed now, back on the resting clay (through the bone it is on)."""
    n = r.bone_at(p)
    return aim.point(aim.compose(r.rest[n], aim.invert(r.frames()[n])), p)


@R.operation("pose.rest", "Take a clay's pose off: without `at`, every Turn key of its joints is removed (back to "
             "the resting shape for the whole shot); with `at` (seconds), the resting turn is keyed at that time on "
             "every joint that has keys (it passes through rest there).", target="clay", label="Pose: back to rest",
             params=[Param.number("at", label="At", min=0, max=36000, step=0.001, unit="s", default=None,
                                  nullable=True, help="Key the rest pose at this time instead of removing the keys")])
def pose_rest(ctx, targets, args):
    for t in targets:
        bones = _all_bones(ctx.item(t))
        if args.get("at") is None:
            ctx.remove_many([k["id"] for b in bones for k in b.get("keys", []) if k["prop"] in TURN])
            continue
        for b in bones:
            if any(keys_of(b, p) for p in TURN):
                for p in TURN:
                    put_key(ctx, b["id"], p, float(args["at"]), {"v": float(b.get(p, 0.0))})


@R.operation("pose.move_joint", "Move a clay's joint by hand (its head, on the resting clay): the bones after it "
             "follow, the bone before it in a chain now ends there, and every bend (key) stays. The joint is marked "
             "placed, so finding the joints again keeps it where you put it.", target="clay", label="Move joint",
             params=[JOINT, WHERE])
def pose_move_joint(ctx, targets, args):
    clay = _one_clay(ctx, targets)
    r = _rig(ctx, clay)
    n = _find(ctx, r, args["joint"])
    joints = PJ.joints_of(clay)
    to = _to_clay(ctx, clay["id"], args["to"])
    move = [b - a for a, b in zip(joints[n]["head"], to)]
    after = {n}
    for i in range(n + 1, len(joints)):                    # parents first: a bone after one that moves moves too
        if r.parent[i] in after:
            after.add(i)
    p = r.parent[n]
    if p >= 0 and PJ._same(joints[p]["tail"], joints[n]["head"]):
        joints[p]["tail"] = list(to)
    for i in after:
        joints[i]["head"] = [a + b for a, b in zip(joints[i]["head"], move)]
        joints[i]["tail"] = [a + b for a, b in zip(joints[i]["tail"], move)]
    joints[n]["placed"] = True
    ids = _write(ctx, clay, joints, clay.get("jointNames", "plain"))
    return {"joints": _reply_joints(ctx, clay["id"], ids)}
