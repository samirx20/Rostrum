"""Pose by dragging (CL5): what breaks silently is a joint tree with the wrong parts (an arm that can't bend at the
elbow, feet hung on the wrong bone), a drag that moves a held foot, and finding the joints again losing a joint
placed by hand or a bend already keyed."""
import base64
import math
import time
import zlib

import numpy as np
from rostrum_core import Document, Who

from rostrum3d import KIND, aim, ops_pose, pose_ik, pose_joints as PJ, run_source
from rostrum3d.compile import describe

SAM = Who.person()


def _capsule(P, a, b, r):
    a, b = np.array(a, float), np.array(b, float)
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
    return np.linalg.norm(P - (a + t[..., None] * ab), axis=-1) - r


def _smin(a, b, k=0.04):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def pear(cells=48):
    """The five-minute character: a pear body, two straight arms joined at its sides, two small feet at its bottom."""
    lo, hi = np.array([-0.75, -0.2, -0.4]), np.array([0.75, 0.9, 0.4])
    cell = (hi - lo).max() / cells
    dims = np.ceil((hi - lo) / cell).astype(int) + 1
    P = np.stack(np.meshgrid(*[lo[i] + np.arange(dims[i]) * cell for i in range(3)], indexing="ij"), -1)
    d = _smin(_capsule(P, [0, 0.3, 0], [0, 0.3, 0], 0.3), _capsule(P, [0, 0.6, 0], [0, 0.6, 0], 0.2), 0.1)
    for s in (1, -1):
        d = _smin(d, _capsule(P, [s * 0.25, 0.55, 0], [s * 0.62, 0.55, 0], 0.055))
        d = _smin(d, _capsule(P, [s * 0.12, 0.02, 0], [s * 0.13, -0.1, 0.06], 0.065), 0.02)
    return {"occupancy": d < 0, "origin": (lo - cell / 2).tolist(), "cell": float(cell)}     # origin: the low corner


EGG = {"origin": [-0.39958331908565015, -0.045383331715129316, -0.17278332717251033], "cell": 0.015983332763426006, "dims": [50, 35, 22],  # the engine's clay_grid of the first real five-minute character
       "bits": (
           "eNrtlztuwzAMhh1o0BLAN4ivkLFT3aP0CB0zFFV6s3Tq2CM0vUGALhqCsNBPDxRM2ZLzLBAODGDKDj+SoqiqukuOGOjZFj8r6AW0XeNn8084ajhq"
           "dqA54JEDQYtH9R5mgoGwtgGz9eKNVpJfNSuSg91ljgaPLAUXZwQC5wcNETmHhMn5P7qcX0I4ujIfkbuERy0crcFsaJdhkORRrDi11V4U9ZkSxdGN"
           "wi7dteRhhqMOjjZYmzQo5FGsZBBPX7v8Ka4SGV32aoyDwNxi7Qi5klqldqPtfBxgtKNkokY4ajhqiAYNyZCcF5Df4GqXieqiK73K4xgxTAYsKFFr"
           "etXOlajsqKkcMFCQjQva24Ojb59bosk9aFJQLw9BPzaJWPUrMclhKSR1RljrsFYAmj3R164G2ie0Z8Dq2dH7egBQaTJRF52n0NZPQfvXxKcKKrFB"
           "UiNAQV7/ErWbFlAM+AG9He2iyjERnYPL4YJkwP7hpfTEiZUoAe2BQiW+NfTjy7ZadNDXBdPbotf05Vl7OsDpx11eJWaNHyOAJc0yq+l3gHJUUxLV"
           "TeHlsurNu1mAR84leYPX/AQDSRag0mQUjuRkmRydL3I3SAGWT8glV4DJBVcuy95kqVzJklcZ5RJ31atM1kSmXEaVO6dsALfGcZfbkD8Y2tzL")}


def test_finder_on_the_engines_grid_finds_both_feet_as_a_pair():
    """The real egg: arms straight out, two small feet mostly sunk into its bottom (they meet under the body, so read
    whole they were one leg). Mirrored, it is read on one half and mirrored: matched .L / .R."""
    bits = np.unpackbits(np.frombuffer(zlib.decompress(base64.b64decode("".join(EGG["bits"]))), np.uint8))
    nx, ny, nz = EGG["dims"]
    grid = {**EGG, "inside": base64.b64encode(bits[:nx * ny * nz].tobytes()).decode()}
    assert PJ.mirrored(grid)
    joints = {j["joint"]: j for j in PJ.find(grid)}
    assert set(joints) - {"head"} == {"body", "chest", "arm.L", "forearm.L", "arm.R", "forearm.R", "foot.L", "foot.R"}
    assert joints["foot.L"]["parent"] == joints["foot.R"]["parent"] == "body"
    for a, b in (("arm.L", "arm.R"), ("forearm.L", "forearm.R"), ("foot.L", "foot.R")):
        for k in ("head", "tail"):
            assert joints[a][k] == [-joints[b][k][0] + 0.0, *joints[b][k][1:]]      # an exact mirrored pair


def _clay(joints):
    """A clay item holding these joints as bones (what pose.find_joints writes), without a document."""
    clay = {"id": "c", "type": "clay", "bones": []}
    made = {}
    for j, v in zip(joints, PJ.rest_bones(joints)):
        made[j["joint"]] = {"id": PJ.bone_id("c", j["joint"]), "type": "bone", "joint": j["joint"], **v,
                            "bones": [], "keys": []}
        (made[j["parent"]]["bones"] if j["parent"] else clay["bones"]).append(made[j["joint"]])
    return clay


def test_finder_names_the_five_minute_character():
    joints = PJ.find(pear())
    tree = {j["joint"]: j["parent"] for j in joints}
    assert tree["body"] is None
    for s in ("L", "R"):
        assert tree[f"foot.{s}"] == "body"
        assert tree[f"forearm.{s}"] == f"arm.{s}" and tree[f"arm.{s}"] in ("body", "chest")
    assert set(tree) <= {"body", "chest", "head", "arm.L", "arm.R", "forearm.L", "forearm.R", "hand.L", "hand.R",
                         "foot.L", "foot.R"}
    by = {j["joint"]: j for j in joints}
    assert by["arm.L"]["head"][0] > 0.1 and by["arm.R"]["head"][0] < -0.1          # +X is .L
    assert by["forearm.L"]["tail"][0] > 0.6 and by["foot.R"]["tail"][1] < -0.05   # to the very tips
    assert 0.3 < by["forearm.L"]["head"][0] < 0.5                                   # an elbow halfway along


def test_drag_bends_shoulder_and_elbow_and_leaves_holds():
    clay = _clay(PJ.find(pear()))
    r = pose_ik.Rig(clay)
    hand = r.find("forearm.R")
    if "hand.R" not in r.joint:                                          # a short arm: its end is still the hand
        assert r.find("hand.R") == hand and r.find("RightHand") == hand
    tip =pose_ik.skin.segment(r.frames()[hand], r.bones[hand])[3:]
    to = [tip[0] + 0.15, tip[1] + 0.3, tip[2] + 0.05]                    # the right hand up and in
    start = time.perf_counter()
    out = pose_ik.solve(clay, PJ.bone_id("c", "forearm.R"), tip, to,
                        holds=["foot.L", "foot.R"])
    ms = (time.perf_counter() - start) * 1000
    assert out["miss"] < 0.01 and ms < 25                                # well under a frame (CI machines are slow)
    assert {"c_arm_R", "c_forearm_R"} <= set(out["moved"])               # shoulder AND elbow
    assert not {"c_body", "c_foot_L", "c_foot_R"} & set(out["moved"])   # feet held: the body (their parent) stays
    pose = pose_ik.chain_pose(clay, out["turns"])
    feet = [r.index[PJ.bone_id("c", f)] for f in ("foot.L", "foot.R")]
    assert all(pose[n][:9] == [1, 0, 0, 0, 1, 0, 0, 0, 1] and pose[n][9:] == [0, 0, 0] for n in feet)
    nothing = pose_ik.solve(clay, "c_forearm_R", tip, to, holds=["forearm.R"])
    assert nothing["moved"] == []                                        # a held part doesn't move


def test_wave_with_only_the_feet_held_leaves_the_body_upright():
    """The real egg, feet held, the right hand dragged up: within the arm's reach only the arm turns (the chest stays
    exactly as it was); far out of reach the chest leans only gently (pose_ik.TRUNK_MAX), never folding the body."""
    bits = np.unpackbits(np.frombuffer(zlib.decompress(base64.b64decode("".join(EGG["bits"]))), np.uint8))
    nx, ny, nz = EGG["dims"]
    clay = _clay(PJ.find({**EGG, "inside": base64.b64encode(bits[:nx * ny * nz].tobytes()).decode()}))
    r = pose_ik.Rig(clay)
    g = r.find("hand.R")
    tip = pose_ik.skin.segment(r.frames()[g], r.bones[g])[3:]
    near = pose_ik.solve(clay, r.ids[g], tip, [tip[0] + 0.03, tip[1] + 0.1, tip[2]], holds=["foot.L", "foot.R"])
    assert near["miss"] < 0.01 and set(near["moved"]) == {"c_arm_R", "c_forearm_R"}
    far = pose_ik.solve(clay, r.ids[g], tip, [tip[0] + 0.03, tip[1] + 0.4, tip[2]], holds=["foot.L", "foot.R"])
    chest = r.index["c_chest"]
    lean = pose_ik._angle(pose_ik._rot(*r.turn[chest]), pose_ik._rot(*pose_ik._as_turn(far["turns"]["c_chest"])))
    assert math.degrees(lean) <= math.degrees(pose_ik.TRUNK_MAX) + 0.1


def _doc(tmp_path):
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("t.py", run_source('''
c = clay("c")
cam = camera("cam", z=3, y=0.4)
shot("s", camera=cam, fps=2, start=0, end=1.0)
''', "t.py"))
    d.apply({"op": "clay.shape", "target": ["c"], "args": {"shape": "sphere", "at": [0, 0.3, 0], "radius": 0.3}}, SAM)
    ops_pose.use_grid(lambda doc, id_, cells: pear(cells))
    d.apply({"op": "pose.find_joints", "target": ["c"]}, SAM)
    return d


def test_refind_keeps_a_placed_joint_and_a_bend(tmp_path):
    d = _doc(tmp_path)
    assert not PJ.out_of_date(d.item("c"), d.data)
    d.apply({"op": "pose.move_joint", "target": ["c"], "args": {"joint": "forearm.L", "to": [0.45, 0.6, 0.0]}}, SAM)
    out = d.apply({"op": "pose.drag", "target": ["c"], "args": {"part": "forearm.L", "to": [0.5, 0.9, 0.1],
                                                                "holds": ["foot.L", "foot.R"], "at": 0.5}}, SAM)
    assert out is not None
    bends = _bends(d)
    assert set(bends) >= {"c_arm_L", "c_forearm_L"}
    elbow = d.item("c_forearm_L")["x"], d.item("c_forearm_L")["y"]
    d.apply({"op": "pose.find_joints", "target": ["c"]}, SAM)                # found again: the shape is the same
    assert d.item("c_forearm_L")["placed"] and (d.item("c_forearm_L")["x"], d.item("c_forearm_L")["y"]) == elbow
    again = _bends(d)                                                        # each bend (turn against rest) kept
    assert set(again) == set(bends) and all(abs(a - b) < 1e-5 for k in bends for a, b in zip(again[k], bends[k]))
    skin = next(i for i in describe(d.data, "s")["items"] if i["id"] == "c")["skin"]
    assert len(skin["rest"]) == len(pose_ik.Rig(d.item("c")).ids) and len(skin["pose"]) == 2
    d.apply({"op": "pose.rest", "target": ["c"]}, SAM)
    assert not any(b.get("keys") for b in ops_pose._all_bones(d.item("c")))
    d.undo(SAM)
    assert any(b.get("keys") for b in ops_pose._all_bones(d.item("c")))
    ops_pose.use_grid(None)


def _bends(d):
    """Each keyed bone's bend at 0.5 s: rest⁻¹ · turn, 9 numbers."""
    r = pose_ik.Rig(d.item("c"), 0.5)
    return {i: sum(aim._mul(pose_ik._t(pose_ik._rot(*rest)), pose_ik._rot(*now)), [])
            for i, rest, now, b in zip(r.ids, r.rest_turn, r.turn, r.bones) if b.get("keys")}


def _grid(fn, lo=(-0.2, -0.02, -0.1), hi=(0.2, 0.28, 0.1), cells=48):
    lo, hi = np.array(lo, float), np.array(hi, float)
    cell = (hi - lo).max() / cells
    dims = np.ceil((hi - lo) / cell).astype(int) + 1
    P = np.stack(np.meshgrid(*[lo[i] + np.arange(dims[i]) * cell for i in range(3)], indexing="ij"), -1)
    return {"occupancy": fn(P) < 0, "origin": (lo - cell / 2).tolist(), "cell": float(cell)}


def _buddy(arm):
    """The guide's 26 cm pear with feet and mirrored arms: arm(P, s) is one arm's distance (s = ±1, its side)."""
    def fn(P):
        d = _smin(_capsule(P, [0, 0.085, 0], [0, 0.085, 0], 0.085), _capsule(P, [0, 0.19, 0], [0, 0.19, 0], 0.06), 0.04)
        for s in (1, -1):
            d = arm(d, P, s)
            d = _smin(d, _capsule(P, [s * 0.04, 0.012, 0.02], [s * 0.045, 0.012, 0.06], 0.015), 0.01)
        return d
    return _grid(fn)


STRAIGHT = lambda d, P, s: _smin(d, _capsule(P, [s * 0.05, 0.17, 0], [s * 0.15, 0.13, 0], 0.018), 0.01)  # noqa: E731
HANGING = lambda d, P, s: np.minimum(_smin(d, _capsule(P, [s * 0.05, 0.19, 0], [s * 0.115, 0.15, 0], 0.017), 0.01),  # noqa: E731
                                     _capsule(P, [s * 0.115, 0.15, 0], [s * 0.12, 0.06, 0.01], 0.016))   # 1 cm off the side


def test_a_straight_long_arm_gets_an_elbow():
    by = {j["joint"]: j for j in PJ.find(_buddy(STRAIGHT))}
    assert by["forearm.R"]["parent"] == "arm.R" and by["arm.R"]["parent"] in ("body", "chest")
    elbow, shoulder, tip = (np.array(by[j][k]) for j, k in (("forearm.R", "head"), ("arm.R", "head"),
                                                            ("forearm.R", "tail")))
    share = np.linalg.norm(elbow - shoulder) / (np.linalg.norm(elbow - shoulder) + np.linalg.norm(tip - elbow))
    assert 0.3 < share < 0.7                                              # about its middle


def test_an_arm_hanging_beside_the_body_is_an_arm():
    by = {j["joint"]: j for j in PJ.find(_buddy(HANGING))}
    assert {"arm.L", "arm.R", "forearm.L", "forearm.R"} <= set(by)
    assert by["forearm.R"]["tail"][1] < 0.1 < by["arm.R"]["head"][1]      # from the shoulder down to the hand


def test_a_raised_arm_leaves_the_body_beyond_the_shoulder():
    """Each piece bends with its own bones (skin_parts): the hip beside a hanging arm is the body's, though the arm's
    bones are nearer it through the air (the flap the plain nearest-bones rule pulled)."""
    from rostrum3d import skin, skin_parts as SP
    joints, parts = PJ.find_parts(_buddy(HANGING))
    clay = _clay(joints)
    clay["jointParts"] = PJ.pack_parts(parts)
    core = skin.skin(clay, [0.0])
    rest, P = core["rest"], core["parts"]
    names = [b.get("joint") for b, _ in pose_ik.skin.bones_of(clay)]
    arm = {names.index(n) for n in names if n.startswith(("arm.", "forearm.", "hand."))}
    hip = [-0.088, 0.09, 0.02]                                            # the body's side, 1-2 cm from the forearm
    assert sum(w for b, w in SP.weights([hip], rest, None)[0].items() if b in arm) > 0.3     # the old rule's flap
    assert not set(SP.weights([hip], rest, P)[0]) & arm
    blend = P["pieces"][P["bone"][names.index("arm.R")]]["blend"]
    pts = np.array(P["origin"]) + (np.argwhere(parts["cells"] == 0) + 0.5) * P["cell"]     # the body's cells
    off = np.min([np.linalg.norm(pts - rest[names.index(f"arm.{s}")][:3], axis=1) for s in "LR"], axis=0)
    far = pts[off > SP.REACH * blend][::7]                                # beyond either shoulder's band (CL7b)
    assert all(not set(w) & arm for w in SP.weights(far, rest, P))
    near = pts[off < blend]                                               # and the shoulders themselves are shared
    assert any(set(w) & arm and set(w) - arm for w in SP.weights(near, rest, P))
    limb = np.array(P["origin"]) + (np.argwhere(np.isin(parts["cells"], [P["bone"][b] for b in arm])) + 0.5) * P["cell"]
    off = np.min([np.linalg.norm(limb - rest[names.index(f"arm.{s}")][:3], axis=1) for s in "LR"], axis=0)
    assert all(set(w) <= arm for w in SP.weights(limb[off > 2 * blend], rest, P))   # an arm is all arm past its
    # shoulder's band (3d-28: the body spread back into it, and the raised upper arm came apart from the shoulder)


def test_a_part_on_the_body_rides_a_body_bone_not_the_arm_beside_it():
    """follow.nearest_bone weighs as the core bends (skin_parts): a part on the body's side (on it, or sitting just
    off its surface) rides the body, though the hanging arm's bone is nearer through the air (the mirrored eye that
    turned with the raised arm)."""
    from rostrum3d import follow
    joints, parts = PJ.find_parts(_buddy(HANGING))
    clay = _clay(joints)
    names = [b.get("joint") for b, _ in pose_ik.skin.bones_of(clay)]
    for spot in ([-0.088, 0.09, 0.02], [-0.088, 0.09, 0.06]):
        assert names[follow.nearest_bone(clay, spot)].startswith("forearm.")         # the plain rule
        clay["jointParts"] = PJ.pack_parts(parts)
        assert not names[follow.nearest_bone(clay, spot)].startswith(("arm.", "forearm.", "hand."))
        del clay["jointParts"]
