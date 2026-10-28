"""faults.py names, in the look and render replies, the faults judges cap a piece for and our agents never noticed:
a part of a figure drifting off its body, a thing floating above the ground, a subject leaving or cut by the frame."""
from rostrum_core import Document, Who
from rostrum_core.mcp import App, Runtime

from rostrum3d import KIND, run_source
from rostrum3d.faults import shot_faults
from rostrum3d.mcp import motion_look

SRC = '''
camera("cam", z=4, y=0.8)
mesh("ground", shape="plane", width=20, depth=20)
mesh("ball", shape="sphere", radius=0.15, x=-0.8, y=0.19)
with group("figure", x=0.3):
    mesh("body", shape="box", width=0.3, height=0.6, depth=0.2, y=0.3)
    mesh("arm", shape="sphere", radius=0.07, x=0.17, y=0.45).key("x", {0: 0.17, 2: 0.5}).key("y", {0: 0.45, 2: 0.07})
mesh("cube", shape="box", width=0.2, height=0.2, depth=0.2, x=0.9, y=0.1).key("z", {0: 0, 2: 2.5})
shot("hero", camera="cam", fps=24, start=0, end=2)
'''


def _doc(src: str) -> Document:
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(src, "s.py"))
    return doc


def test_a_floating_ball_a_drifting_arm_and_a_cube_leaving_the_frame_are_named():
    lines = shot_faults(_doc(SRC).data, "hero")
    text = " | ".join(lines)
    assert any(x.startswith("Part arm separates from body at 0.4 s") for x in lines), text
    assert any(x.startswith("ball floats 4 cm above ground") for x in lines), text
    assert any(x.startswith("cube leaves the frame (bottom)") for x in lines), text
    reply = Runtime(App("rostrum-3d", {"scene": _doc(SRC)}), motion_look.tools).call("look_motion", {}, Who.agent("t"))[0]
    assert "Fault: ball floats 4 cm" in reply["summary"] and reply["data"]["faults"] == lines


def test_a_still_scene_resting_on_the_ground_and_in_frame_is_silent():
    still = SRC.replace("y=0.19", "y=0.15").replace('.key("x", {0: 0.17, 2: 0.5}).key("y", {0: 0.45, 2: 0.07})', "")
    still = still.replace('.key("z", {0: 0, 2: 2.5})', "")
    assert shot_faults(_doc(still).data, "hero") == []
    assert shot_faults(_doc(still).data, "hero", at=30) == []
