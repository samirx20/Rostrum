"""A combine stays live: its inputs remain items, so moving the cutter changes what the core is asked to cut, and undo
takes each step back (SPEC §4.2). The cut itself is the core's (Manifold); here, what the document sends it."""
import pytest
from rostrum_core import Document, Who
from rostrum_core.errors import RostrumError

from rostrum3d import KIND, run_source
from rostrum3d.compile import describe

SAM = Who.person()
SRC = '''
mesh("case", shape="box", width=0.064, height=0.03, depth=0.048, bevel=0.004)
mesh("port", shape="cylinder", radius=0.004, height=0.03, rx=90, x=0.0, z=0.02)
cam = camera("cam", z=0.4)
shot("hero", camera=cam, fps=24, start=0, end=1)
'''


def _combine(d):
    return next(n for n in describe(d.data, "hero")["items"] if n["type"] == "combine")


def test_a_combine_stays_live_and_undo_takes_it_back():
    d = Document.new(KIND)
    d.run_script("case.py", run_source(SRC, "case.py"))
    d.apply({"op": "combine.make", "target": ["case", "port"], "args": {"op": "subtract"}}, SAM)
    node = _combine(d)
    assert (node["props"]["op"], [c["id"] for c in node["children"]]) == ("subtract", ["case", "port"])
    assert d.item(node["id"])["name"] == "case"                          # the result takes the base's name

    d.apply({"op": "mesh.set", "target": ["port"], "args": {"x": 0.02}}, SAM)
    assert _combine(d)["children"][1]["props"]["x"] == 0.02             # moving the cutter moves the hole

    d.undo(SAM)
    assert _combine(d)["children"][1]["props"]["x"] == 0.0
    d.undo(SAM)                                                          # the combine itself is one undo step
    assert [n["type"] for n in describe(d.data, "hero")["items"]][:2] == ["mesh", "mesh"]


def test_a_combines_inputs_cant_be_animated_or_too_few():
    d = Document.new(KIND)
    d.run_script("case.py", run_source(SRC, "case.py"))
    with pytest.raises(RostrumError, match="two or more"):
        d.apply({"op": "combine.make", "target": ["case"], "args": {}}, SAM)
    d.apply({"op": "combine.make", "target": ["case", "port"], "args": {}}, SAM)
    with pytest.raises(RostrumError, match="can't be animated"):
        d.apply({"op": "key.add", "target": ["port"], "args": {"prop": "x", "t": 0.5, "v": 0.01}}, SAM)
