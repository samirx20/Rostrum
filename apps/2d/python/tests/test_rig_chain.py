"""Long IK chains are solved in Python (rig/chain.py) on top of a Python copy of the engine's FK (rig/fk.py): the
copy must agree with the engine, or a chain's base would be wrong without anything saying so. Poses: save, apply and
blend keys the rig in one step."""
import os

import pytest
from rostrum_core import Document, Who

from rostrum2d import KIND, run_source
from rostrum2d.rig import chain, fk
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


def test_a_long_chain_reaches_its_target_and_its_ik_stays_off_the_engine():
    rig = doc().item("pup")
    for t in (0, 0.5, 1):
        posed = fk.pose(rig, t, turns=chain.solve(rig, t, {}))
        assert fk.tip(posed["d"]) == pytest.approx(chain.target(rig["iks"][0], t), abs=0.05)
    scene = describe(doc().data)
    nodes = scene["comp"]["layers"][0]["rig"]
    assert not [n for n in nodes if n["type"] == "ik"]
    assert len(next(n for n in nodes if n["id"] == "a")["anim"]["rotation"]) == 11


@pytest.mark.skipif(not os.environ.get("ROSTRUM2D_ENGINE"), reason="needs a built engine (ROSTRUM2D_ENGINE)")
def test_python_fk_matches_the_engine():
    from rostrum2d.engine import Engine
    d = doc()
    rig = d.item("pup")
    with Engine() as eng:
        eng.load(describe(d.data))
        for t in (0.3, 1.0):
            got = eng.bones(t)["pup"]["bones"]
            posed = fk.pose(rig, t, turns=chain.solve(rig, t, {}))
            for id_ in ("a", "b", "c", "d"):           # rig at x=400, y=400, box 800: rig px = comp px
                assert (got[id_]["tipX"], got[id_]["tipY"]) == pytest.approx(fk.tip(posed[id_]), abs=0.05)


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
