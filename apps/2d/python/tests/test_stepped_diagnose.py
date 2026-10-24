"""Stepped timing is an evaluation setting (the person's keys never change; turning it off gives the smooth motion
back), and inspect_diagnose's document checks name what is wrong."""
import copy

from rostrum_core import Document

from rostrum2d import KIND, diagnose, run_source
from rostrum2d.scene import describe

SRC = '''
comp("c", width=320, height=180, fps=10, duration=1, timing="2")
dot = shape("dot", w=10, h=10, y=90)
dot.key("x", {0: 0, 1: 100}, ease="linear")
smooth = shape("smooth", w=10, h=10, timing="1")
smooth.key("x", {0: 0, 1: 100}, ease="linear")
'''


def doc(src=SRC):
    d = Document.new(KIND)
    d.run_script("s.py", run_source(src, "s.py"))
    return d


def layer(scene, id_):
    return next(n for n in scene["comp"]["layers"] if n["id"] == id_)


def test_on_twos_holds_each_pose_and_leaves_the_keys_alone():
    d = doc()
    before = copy.deepcopy(d.data)
    scene = describe(d.data)
    assert d.data == before                                    # the document is untouched
    keys = layer(scene, "dot")["anim"]["x"]
    assert [k["t"] for k in keys] == [k * 2 / 10 for k in range(6)] and {k["ease"] for k in keys} == {"hold"}
    assert [k["v"] for k in keys] == [0, 20, 40, 60, 80, 100]
    assert layer(scene, "smooth")["anim"]["x"][1]["ease"] == "linear"     # its own setting wins over the comp's
    assert "timing" not in layer(scene, "dot")["props"]                   # the engine never sees the setting


def test_diagnose_names_what_is_wrong():
    d = doc(SRC + '''
ghost = shape("ghost", w=10, h=10, opacity=0)
beside = shape("beside", w=10, h=10, x=2000)
late = shape("late", w=10, h=10)
late.key("y", {0: 0, 5: 50})
m = shape("m", w=10, h=10, matte="nobody")
m.expr("opacity", "1 if time > marker('drop') else 0")
''')
    found = {(p["kind"], p["item"]) for p in diagnose.problems(d.data["comps"][0], None, {"intro": 0.5})}
    assert {("invisible", "ghost"), ("unused-keys", "late"), ("broken-link", "m"), ("missing-marker", "m")} <= found
    assert not any(item == "beside" for _, item in found)      # beside the frame is a place in the world, not a problem
