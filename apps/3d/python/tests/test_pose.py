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
