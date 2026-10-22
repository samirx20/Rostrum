"""Characters on the screen (H32): Bones from part names makes a valid rig with every part bound; fixing a joint keeps
the bones joined; a swap set made inside a rig still follows its bone; a pose drag is one undo step."""
import math

from rostrum_core import Document, Who

from rostrum2d import KIND, run_source
from rostrum2d.rig.model import tip

SAM = Who.person("sam")
PARTS = [("torso", 640, 330, 130, 180), ("head", 640, 180, 110, 120), ("upper arm L", 558, 290, 30, 100),
         ("forearm L", 558, 385, 26, 90), ("hand L", 558, 450, 34, 40), ("thigh R", 670, 470, 40, 100),
         ("shin R", 670, 565, 34, 90), ("foot R", 682, 625, 60, 28), ("mouth A", 640, 214, 40, 28),
         ("mouth rest", 640, 212, 40, 5)]


def rigged():
    src = 'comp("c", width=1280, height=720, duration=3)\nwith group("max", name="max"):\n' + "".join(
        f'    shape("{n.replace(" ", "_")}", name="{n}", x={x}, y={y}, w={w}, h={h})\n' for n, x, y, w, h in PARTS)
    d = Document.new(KIND)
    d.run_script("max.py", run_source(src, "max.py"))
    d.apply({"op": "rig.make", "target": ["max"], "args": {"id": "r"}}, SAM)
    d.apply({"op": "rig.guess_bones", "target": ["r"], "args": {}}, SAM)
    return d


def bone(d, name):
    return next(b for b in d.item("r")["bones"] if b["name"] == name)


def test_bones_from_part_names_bind_every_part_and_chain_the_limbs():
    d = rigged()
    r = d.item("r")
    assert {lay["id"] for lay in r["layers"]} == {b["layer"] for b in r["binds"]}     # one group became the rig
    assert bone(d, "forearm L")["parent"] == bone(d, "upper arm L")["id"]
    assert math.dist(tip(bone(d, "upper arm L")), (bone(d, "forearm L")["x"], bone(d, "forearm L")["y"])) < 0.01
    assert {k["bone"] for k in r["iks"]} == {bone(d, "forearm L")["id"], bone(d, "shin R")["id"]}
    mouth = next(b for b in r["binds"] if b["layer"] == "mouth_A")
    assert mouth["bone"] == bone(d, "head")["id"]


def test_moving_a_joint_keeps_the_parent_ending_there_and_the_bone_tip_still():
    d = rigged()
    fore, was = bone(d, "forearm L"), tip(bone(d, "forearm L"))
    d.apply({"op": "rig.move_joint", "target": [fore["id"]], "args": {"x": 50, "y": 230}}, SAM)
    fore, upper = bone(d, "forearm L"), bone(d, "upper arm L")
    assert math.dist(tip(upper), (50, 230)) < 0.05 and math.dist(tip(fore), was) < 0.05


def test_a_swap_set_made_inside_a_rig_follows_the_bone_its_drawings_followed():
    d = rigged()
    d.apply({"op": "group.make", "target": ["mouth_A", "mouth_rest"], "args": {"as": "swap", "id": "mouth"}}, SAM)
    binds = {b["layer"]: b["bone"] for b in d.item("r")["binds"]}
    assert binds["mouth"] == bone(d, "head")["id"] and "mouth_A" not in binds


def test_a_pose_drag_is_one_undo_step():
    d = rigged()
    ik = d.item("r")["iks"][0]["id"]
    d.apply({"op": "rig.key", "target": ["r"], "args": {"t": 1.0}}, SAM)
    before = d.item(ik)
    with d.gesture("Pose arm", SAM) as g:
        for dx in (10, 20, 30):
            g.preview([{"op": "value.set", "target": [ik], "args": {"prop": "targetX", "at": 1.0, "v": before["targetX"] + dx}}])
    assert d.item(ik) != before
    d.undo(SAM)
    assert d.item(ik) == before
