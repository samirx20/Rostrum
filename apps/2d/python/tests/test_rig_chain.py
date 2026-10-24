"""Long IK chains are the engine's (rig/fabrik.rs): the scene sends the ik with its `chain`, and the engine's `bones`
answer reports the chain reaching its target, so look_rig and inspect_rig_motion see it. Poses: save, apply and blend
keys the rig in one step."""

import pytest
from rostrum_core import Document, Who

from rostrum2d import KIND, run_source, settings
from rostrum2d.scene import describe

SAM = Who.person("sam")
SRC = '''
comp("shot", duration=1, fps=10)
with rig("pup", w=800, h=800, x=400, y=400):
    hip = bone("hip", x=400, y=300, angle=0, length=0)
    hip.key("moveX", {0: 0, 1: 60}).key("rotation", {0: 0, 1: 15})
    a = bone("a", parent=hip, angle=90, length=100)
    b = bone("b", parent=a, length=90)
    b.key("scale", {0: 1, 1: 1.2})
    c = bone("c", parent=b, length=80)
    d = bone("d", parent=c, length=60)
    tail = ik("tail", bone=d, chain=4)
    tail.key("targetX", {0: 520, 1: 380}).key("targetY", {0: 520, 1: 560})
'''


def doc():
    d = Document.new(KIND)
    d.run_script("t.py", run_source(SRC, "t.py"))
    return d


@pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")
def test_the_engine_solves_a_long_chain_and_reports_it():
    from rostrum2d.engine import Engine
    scene = describe(doc().data)
    tail = next(n for n in scene["comp"]["layers"][1]["rig"] if n["id"] == "tail")
    assert tail["props"]["chain"] == 4
    with Engine() as eng:
        eng.load(scene)
        for t in (0.0, 0.5, 1.0):
            ik = eng.bones(t)["pup"]["iks"]["tail"]
            assert ik["gap"] < 0.05 and ik["bones"] == ["a", "b", "c", "d"]


def test_poses_save_apply_and_blend():
    d = doc()
    d.apply({"op": "pose.save", "target": "pup", "args": {"id": "start", "t": 0}}, SAM)
    d.apply({"op": "pose.save", "target": "pup", "args": {"id": "end", "t": 1}}, SAM)
    seq = d.history.seq
    d.apply({"op": "pose.apply", "target": "pup", "args": {"pose": "start", "with": "end", "mix": 0.5, "t": 2}}, SAM)
    hip = d.item("hip")
    at2 = {k["prop"]: k["v"] for k in hip["keys"] if k["t"] == 2}
    assert at2["moveX"] == pytest.approx(30) and at2["rotation"] == pytest.approx(7.5)
    assert len(d.history.since(seq)) == 1                                   # one undo step


def test_a_pose_is_renamed_by_the_one_rename_operation():
    d = doc()
    d.apply({"op": "pose.save", "target": "pup", "args": {"id": "start", "name": "Pose", "t": 0}}, SAM)
    d.apply({"op": "item.rename", "target": "start", "args": {"name": "Crouch"}}, SAM)
    assert d.item("start")["name"] == "Crouch"
    d.apply({"op": "pose.apply", "target": "pup", "args": {"pose": "Crouch", "t": 1}}, SAM)   # found by its new name
