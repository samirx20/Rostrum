"""rostrum3d/faults.py: the document faults judges cap a piece for, in the shot's one fault list (mcp/shot_faults.check):
a part of a figure coming apart, a subject leaving the picture, no floor in the picture; ids stable across re-runs."""
from rostrum_core import Document, Who
from rostrum_core.mcp import App, Runtime

from rostrum3d import KIND, run_source
from rostrum3d.compile import shot_info
from rostrum3d.mcp import motion_look, shot_faults

SRC = '''
camera("cam", z=4, y=0.8)
mesh("ground", shape="plane", width=20, depth=20)
with group("figure", x=0.3):
    mesh("body", shape="box", width=0.3, height=0.6, depth=0.2, y=0.3)
    mesh("arm", shape="sphere", radius=0.07, x=0.17, y=0.45).key("x", {0: 0.17, 2: 0.5}).key("y", {0: 0.45, 2: 0.07})
mesh("cube", shape="box", width=0.2, height=0.2, depth=0.2, x=0.9, y=0.1).key("z", {0: 0, 2: 2.5})
shot("hero", camera="cam", fps=24, start=0, end=2)
'''


def _faults(src: str) -> dict:
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(src, "s.py"))
    info = shot_info(doc.data, "hero")
    return {f["id"]: f for f in shot_faults.check(doc.data, info, shot_faults.sample(info), {})}, doc


def test_a_drifting_arm_and_a_cube_leaving_are_faults_in_the_one_list_and_open_look_motion():
    found, doc = _faults(SRC)
    assert "separated:arm" in found and "cm gap" in found["separated:arm"]["what"], found
    assert "leaves_frame:cube" in found and "cut_edge:cube" not in found, found     # one fault per thing
    rt = Runtime(App("rostrum-3d", {"scene": doc}), motion_look.tools)
    reply = rt.call("look_motion", {}, Who.agent("t"))[0]
    assert "notes" not in reply and "[separated:arm]" not in reply["summary"]          # checks only when asked
    reply = rt.call("look_motion", {"notes": True}, Who.agent("t"))[0]
    last = reply["summary"].split("\n")[-1]
    assert last.startswith("Notes (") and "[separated:arm]" in last and "NOT DONE" not in reply["summary"], last[:300]


def test_still_and_in_frame_is_done_and_a_camera_looking_up_has_no_floor():
    still = SRC.replace('.key("x", {0: 0.17, 2: 0.5}).key("y", {0: 0.45, 2: 0.07})', "").replace('.key("z", {0: 0, 2: 2.5})', "")
    found, _ = _faults(still)
    assert not [i for i in found if i.split(":")[0] in ("separated", "leaves_frame", "no_floor")], found
    sky = still.replace('camera("cam", z=4, y=0.8)', 'camera("cam", z=4, y=0.8, rx=25)')
    found, _ = _faults(sky)
    assert "no_floor:hero" in found, found


def test_a_seen_sky_photo_past_the_floor_is_a_backdrop_edge_and_an_unseen_one_is_not():
    """Drape (round 5): a low camera saw the Studio photo's room above the floor's far edge."""
    still = SRC.replace('.key("x", {0: 0.17, 2: 0.5}).key("y", {0: 0.45, 2: 0.07})', "").replace('.key("z", {0: 0, 2: 2.5})', "")
    seen = still + 'light("sky", kind="dome", texture="sky:studio")\n'
    found, _ = _faults(seen)
    assert "backdrop_edge:sky" in found and "fix" not in found["backdrop_edge:sky"], found
    found, _ = _faults(seen.replace('texture="sky:studio"', 'texture="sky:studio", seenByCamera=False'))
    assert "backdrop_edge:sky" not in found, found
    found, _ = _faults(seen.replace('camera("cam", z=4, y=0.8)', 'camera("cam", z=4, y=2.5, rx=-35)'))
    assert "backdrop_edge:sky" not in found, found                          # looking down: all floor


def test_a_falling_cloth_or_ball_is_not_floating_but_a_hovering_still_thing_is():
    """Drape (3E round): "sheet floats 0.49 m above box" on a cloth's first frame, before it fell, held a delivery."""
    src = '''
camera("cam", z=4, y=0.8)
mesh("box", shape="box", width=0.4, height=0.45, depth=0.4, x=-0.6).simulate("still")
sheet = mesh("sheet", shape="plane", width=0.8, depth=0.8, x=-0.6)
sheet.simulate("cloth", over="box", fallStart=0.5)
mesh("ball", shape="sphere", radius=0.1, x=0.1, y=0.8).simulate("falls")
mesh("lamp", shape="sphere", radius=0.1, x=0.6, y=0.5)
shot("hero", camera="cam", fps=24, start=0, end=2)
'''
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(src, "s.py"))
    info = shot_info(doc.data, "hero")
    for frames in ([0], shot_faults.sample(info)):               # the first frame alone, and the usual three
        found = {f["id"] for f in shot_faults.check(doc.data, info, frames, {})}
        assert "floating:lamp" in found, found                   # a still thing in the air is still called
        assert "floating:sheet" not in found and "floating:ball" not in found, found
    # from the stored fall: judged only once it stops moving
    fall = {"x": [0.1] * 3, "y": [0.8, 0.4, 0.4], "z": [0.0] * 3, "rx": [0.0] * 3, "ry": [0.0] * 3, "rz": [0.0] * 3}
    assert not shot_faults.settled(fall, 0) and shot_faults.settled(fall, 1) and not shot_faults.settled(None, 1)
