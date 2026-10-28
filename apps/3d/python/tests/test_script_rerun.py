"""Write the scene as one script, look, edit, re-run (script_rerun.py): what would break silently is a re-run that wipes a
person's edit, doubles a key, sticks after an undo, or takes out the rest of the scene for a one-line tweak."""
import pytest
from rostrum_core import Document, Who
from rostrum_core.errors import RostrumError

from rostrum3d import KIND, run_source

SAM = Who.person()
SRC = '''
material("paint", baseColor="#cc3322")
mesh("wall", shape="box", width=2, height=1, depth=0.05, z=-0.5)
ball = mesh("ball", shape="sphere", radius=0.1, y=0.1, material="paint")
ball.key("y", {0: 0.5, 1: 0.1})
cam = camera("cam", z=2).aim(ball)
cam.key("x", {0: -0.3, 2: 0.3})
shot("hero", camera=cam, end=2)
'''


def run(d, src, name="scene.py"):
    return d.run_script(name, run_source(src, name, d))


def _doc():
    d = Document.new(KIND)
    run(d, SRC)
    return d


def test_an_edited_rerun_replaces_its_own_things_and_keeps_a_persons_edit():
    d = _doc()
    d.apply({"op": "mesh.set", "target": ["wall"], "args": {"x": 0.4}}, SAM)
    report = run(d, SRC.replace("radius=0.1", "radius=0.2").replace("{0: -0.3, 2: 0.3}", "{0: -0.5, 1.5: 0.5}"))
    assert d.item("ball")["radius"] == 0.2 and d.item("wall")["x"] == 0.4 and not report.held
    assert sorted((k["t"], k["v"]) for k in d.item("cam")["keys"]) == [(0, -0.5), (1.5, 0.5)]


def test_a_one_line_tweak_under_the_same_name_is_refused_not_a_wipe():
    d = _doc()
    with pytest.raises(RostrumError, match='would remove 4 of the 5 things.*"wall"'):
        run(d, 'edit("ball", y=0.3)')
    assert d.item("wall") and d.item("ball")["y"] == 0.2                  # nothing changed (base 0.1 up: middle 0.2)
    run(d, SRC.replace('mesh("wall", shape="box", width=2, height=1, depth=0.05, z=-0.5)\n', ""))   # one left out: removed
    assert all(i["id"] != "wall" for i in d.data["items"])


def test_edit_twice_and_keys_on_another_scripts_item_and_item_handle():
    d = _doc()
    report = run(d, 'c = edit("cam", z=3)\nedit("cam").key("x", {0: 1, 2: -1})\nitem("ball").set(y=0.4)', "tweak.py")
    assert not report.held and d.item("cam")["z"] == 3 and d.item("ball")["y"] == 0.4
    assert sorted((k["t"], k["v"]) for k in d.item("cam")["keys"]) == [(0, 1), (2, -1)]
    report = run(d, SRC.replace("x\", {0: -0.3", "x\", [{\"t\": 0, \"v\": -0.2}, {\"at\": 2, \"v\": 0.2}], ease=\"smooth\") #"))
    assert not report.held and d.item("cam")["z"] == 2                     # the first script takes them back, cleanly


def test_a_rerun_after_undo_lands_instead_of_holding_everything_back():
    d = _doc()
    d.apply({"op": "mesh.set", "target": ["wall"], "args": {"x": 0.4}}, SAM)
    d.script_bases.pop("scene.py")                                        # an undo or a failed run left no record
    report = run(d, SRC.replace("y=0.1, material", "y=0.25, material"))
    assert not report.held and d.item("ball")["y"] == 0.35 and d.item("wall")["x"] == 0.4
    assert len([i for i in d.data["items"] if i["id"] == "ball"]) == 1
    run(d, 'mesh(shape="box")', "extra.py")
    report = run(d, 'mesh(shape="box")', "more.py")                       # a counted id skips what is there
    assert {"mesh_1", "mesh_2"} <= {i["id"] for i in d.data["items"]} and not report.held


@pytest.mark.xfail(strict=True, reason="KNOWN OPEN (shared merge): a script that replaces the start lights and removes the "
                   "start camera gets 'held back: changed by script:start.py' on the camera; harmless, the agent's own camera is used")
def test_replacing_the_start_lights_and_removing_its_camera_holds_nothing_back():
    from rostrum3d.start_scene import SOURCE as START
    d = Document.new(KIND)
    d.run_script("start.py", run_source(START, "start.py"))          # as the server starts a new scene
    report = run(d, 'light("key", kind="rect", width=0.6, height=0.6, intensity=40, x=-1.4, y=0.45, z=0.5, replace_start_lights=True)\n'
                    'cam = camera("cam", focalLength=50)\nshot("shot_1", camera=cam, end=10)\nremove("shot_1_camera")')
    assert not report.held, report.held
