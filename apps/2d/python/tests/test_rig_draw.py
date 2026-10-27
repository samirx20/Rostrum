"""The Bone tool's operation and Mirror pose (H33): bones drawn joint by joint chain and branch, and attach the parts
they run through; mirroring keys the other side with turns and sideways moves reversed, in one undo step."""
from rostrum_core import Document, Who

from rostrum2d import KIND, boxes, run_source
from rostrum2d.evaluate import value_at

SAM = Who.person("sam")
PARTS = [("torso", 640, 330, 130, 180), ("upper arm L", 558, 290, 30, 100), ("upper arm R", 722, 290, 30, 100),
         ("forearm L", 558, 385, 26, 90), ("forearm R", 722, 385, 26, 90)]


def rig():
    src = 'comp("c", width=1280, height=720, duration=3)\nwith group("max", name="max"):\n' + "".join(
        f'    shape("{n.replace(" ", "_")}", name="{n}", x={x}, y={y}, w={w}, h={h})\n' for n, x, y, w, h in PARTS)
    d = Document.new(KIND)
    d.run_script("max.py", run_source(src, "max.py"))
    d.apply({"op": "rig.make", "target": ["max"], "args": {"id": "r"}}, SAM)
    return d


def draw(d, a, b):
    d.apply({"op": "bone.draw", "target": ["r"], "args": {"x": a[0], "y": a[1], "tipX": b[0], "tipY": b[1]}}, SAM)
    return d.item("r")["bones"][-1]


def down_the(d, name):
    """A bone from the top to the bottom of a part's box, through its middle (rig px)."""
    x0, y0, x1, y1 = boxes.box(next(lay for lay in d.item("r")["layers"] if lay["name"] == name), 0.0)
    return ((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)


def test_bones_drawn_chain_branch_and_attach_the_parts_they_run_through():
    d = rig()
    a, b = down_the(d, "upper arm L")
    upper = draw(d, a, b)
    fore = draw(d, (b[0] + 0.5, b[1] + 0.5), down_the(d, "forearm L")[1])      # a click near the tip: a chain
    branch = draw(d, a, (a[0] - 50, a[1]))                                     # from the first joint: beside it
    assert (fore["parent"], fore["x"], fore["y"]) == (upper["id"], b[0], b[1])
    assert branch["parent"] == upper["parent"] == ""
    binds = {x["layer"]: x["bone"] for x in d.item("r")["binds"]}
    assert binds == {"upper_arm_L": upper["id"], "forearm_L": fore["id"]}         # the branch grazes nothing


def test_mirror_pose_keys_the_other_side_reversed_in_one_step():
    d = rig()
    left, right = draw(d, *down_the(d, "upper arm L")), draw(d, *down_the(d, "upper arm R"))   # sides from their parts
    d.apply({"op": "value.set", "target": [left["id"]], "args": {"prop": "rotation", "at": 1.0, "v": 30}}, SAM)
    d.apply({"op": "value.set", "target": [left["id"]], "args": {"prop": "moveX", "at": 1.0, "v": 12}}, SAM)
    d.apply({"op": "pose.mirror", "target": ["r"], "args": {"t": 1.0}}, SAM)
    r = d.item(right["id"])
    assert (value_at(r, "rotation", 1.0), value_at(r, "moveX", 1.0)) == (-30, -12)
    d.undo(SAM)
    assert value_at(d.item(right["id"]), "rotation", 1.0) == 0


def test_mirror_after_a_pose_adds_no_flat_keys():
    """A pose keys the right side at 0; mirroring a still left side at 1 must not add a second key of the same value
    (the Problems chip listed every such field as "keys that do nothing")."""
    from rostrum2d import diagnose
    d = rig()
    left, right = draw(d, *down_the(d, "upper arm L")), draw(d, *down_the(d, "upper arm R"))
    d.apply({"op": "pose.save", "target": "r", "args": {"id": "rest", "t": 0}}, SAM)
    d.apply({"op": "pose.apply", "target": "r", "args": {"pose": "rest", "t": 0}}, SAM)
    d.apply({"op": "value.set", "target": [left["id"]], "args": {"prop": "rotation", "at": 1.0, "v": 30}}, SAM)
    d.apply({"op": "pose.mirror", "target": ["r"], "args": {"t": 1.0}}, SAM)
    assert value_at(d.item(right["id"]), "rotation", 1.0) == -30
    assert [p["message"] for p in diagnose.problems(d.data["comps"][0]) if p["kind"] == "unused-keys"] == []
