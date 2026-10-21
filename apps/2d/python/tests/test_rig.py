"""Rigs: operations build one and the scene shows it; a script re-run keeps a person's foot-target key; a bind to
a bone that isn't there is refused."""
import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum2d import KIND, run_source
from rostrum2d.scene import describe

SAM = Who.person("sam")
SRC = '''
comp("c", duration=3)
with rig("puppet", w=600, h=800):
    hip = bone("hip", x=300, y=400, angle=90, length=0)
    thigh = bone("thigh", parent=hip, angle=90, length=180)
    shin = bone("shin", parent=thigh, length=170)
    foot = ik("foot_ik", bone=shin)
    foot.key("targetX", {0: 300, 1: 360}, ease="smooth")
    leg = shape("leg", w=60, h=350)
    bind(layer=leg, bone=thigh, bone2=shin)
'''


def doc():
    d = Document.new(KIND)
    d.run_script("rig.py", run_source(SRC, "rig.py"))
    return d


def test_operations_build_a_rig_and_the_scene_shows_it():
    d = Document.new(KIND)
    d.apply({"op": "comp.add", "args": {"id": "c"}}, SAM)
    d.apply({"op": "layer.add", "target": "c", "args": {"type": "rig", "id": "r"}}, SAM)
    d.apply({"op": "layer.add", "target": "r", "args": {"type": "shape", "id": "arm"}}, SAM)
    d.apply({"op": "bone.add", "target": "r", "args": {"id": "upper", "x": 100, "y": 50, "angle": 90, "length": 80}}, SAM)
    d.apply({"op": "bone.add", "target": "r", "args": {"id": "lower", "parent": "upper", "length": 60}}, SAM)
    d.apply({"op": "ik.add", "target": "r", "args": {"bone": "lower", "id": "reach"}}, SAM)
    d.apply({"op": "bind.add", "target": "r", "args": {"layer": "arm", "bone": "upper", "bone2": "lower"}}, SAM)
    lower, reach = d.item("lower"), d.item("reach")
    assert (lower["x"], lower["y"], lower["angle"]) == (100, 130, 90)         # starts at the parent's tip
    assert (reach["targetX"], reach["targetY"]) == (100, 190)                 # target starts at the chain's tip
    rig = describe(d.data)["comp"]["layers"][0]
    assert [(n["type"], n["id"]) for n in rig["rig"]] == [("bone", "upper"), ("bone", "lower"), ("ik", "reach"),
                                                          ("bind", "bind_1")]
    assert rig["rig"][2]["props"]["mode"] == "ik" and rig["layers"][0]["id"] == "arm"
    d.apply({"op": "bone.remove", "target": "upper"}, SAM)                    # takes its chain and bind too
    assert [i["id"] for i in d.item("r")["bones"]] == ["lower"] and not d.item("r")["iks"] + d.item("r")["binds"]
    assert d.item("lower")["parent"] == ""


def test_rerun_keeps_a_persons_foot_target_key():
    d = doc()
    d.apply({"op": "value.set", "target": "foot_ik", "args": {"prop": "targetX", "at": 1, "v": 420}}, SAM)
    report = d.run_script("rig.py", run_source(SRC.replace("1: 360", "1: 380").replace("w=60", "w=70"), "rig.py"))
    assert d.item("foot_ik.targetX.k1000")["v"] == 420 and d.item("leg")["w"] == 70
    assert [h["key"] for h in report.held] == ["foot_ik.targetX.k1000.v"]


def test_a_bind_to_an_unknown_bone_is_refused():
    d = doc()
    with pytest.raises(RostrumError, match='bone2 "shn"'):
        d.apply({"op": "bind.set", "target": "bind_1", "args": {"bone2": "shn"}}, SAM)
    with pytest.raises(RostrumError, match="circle"):
        d.apply({"op": "bone.set", "target": "hip", "args": {"parent": "shin"}}, SAM)
