"""Critic 3d-final fixes agents rely on: a cloth placed over its target and a warning when it ends on nothing (item 5); a fall's
start time reaching the core, and a script replacing the new scene's own things in one undo step (item 7). No engine."""
from __future__ import annotations

import struct

from rostrum_core import Document

from rostrum3d import KIND, run_source
from rostrum3d.sim import cloth_check
from rostrum3d.sim.inputs import sim_inputs
from rostrum3d.sim.result import cloth_file
from rostrum3d.start_scene import SOURCE as START

SCENE = '''
cam = camera("cam", z=3, y=1)
shot("s", camera=cam, fps=24, start=0, end=2)
box = mesh("box", shape="box", width=0.4, height=0.5, depth=0.4, x=1, y=0.25).simulate("still")
sheet = mesh("sheet", shape="plane", width=0.3, depth=0.3, x=-2, y=2).simulate("cloth", over=box)
mesh("ball", shape="sphere", radius=0.1, y=1).simulate("falls", fallStart=1.0)
mesh("cube", shape="box", width=0.1, height=0.1, depth=0.1, x=2, y=1).simulate("falls")
'''


def test_cloth_over_its_target_and_a_warning_when_it_slides_off(tmp_path):
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SCENE, "s.py"))
    sheet = next(i for i in d.data["items"] if i["id"] == "sheet")
    assert (sheet["x"], sheet["z"]) == (1.0, 0.0) and 0.5 < sheet["y"] < 0.7     # centred, a little over the top
    assert sheet["width"] == sheet["depth"] == 0.8                               # too small: twice the footprint
    n, frames = 5, 49                                         # a stored drape that ends 2 m to the side, on the floor
    first = [(-0.4, 0, -0.4), (0.4, 0, -0.4), (0.4, 0, 0.4), (-0.4, 0, 0.4), (0, 0, 0)]
    last = [(x - 2, -sheet["y"], z) for x, _, z in first]
    pts = [c for f in range(frames) for p in (first if f < frames - 1 else last) for c in p]
    (tmp_path / cloth_file("sheet")).write_bytes(b"RCL1" + struct.pack("<4i", n, 2, frames, 0) + struct.pack("<6i", 0, 1, 2, 0, 2, 3)
                                                 + struct.pack(f"<{2 * n}f", *[0.0] * 2 * n) + struct.pack(f"<{len(pts)}f", *pts))
    info = {"id": "s", "start": 0, "end": 48, "fps": 24}
    parts, warns, facts = cloth_check.report(d.data, info, tmp_path)
    assert facts[0]["startsOver"] == ["box"] and facts[0]["endsOn"] == [] and "nothing but the ground" in parts[0]
    assert len(warns) == 1 and "slid off" in warns[0]


def test_fall_start_reaches_the_core_and_a_script_replaces_the_new_scene():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SCENE, "s.py"))
    req, key = sim_inputs(d.data, "s")
    by = {b["item"]: b for b in req["bodies"]}
    assert by["ball"]["wakeFrame"] == 24 and "wakeFrame" not in by["cube"]   # unset: not sent (older results keep their key)

    n = Document.new(KIND)
    n.run_script("start.py", run_source(START, "start.py"))
    src = ('cam = camera("cam", z=2)\nshot("shot_1", camera=cam, end=2)\nlight("sky", kind="dome", intensity=0.3)\n'
           'edit("ground_material", baseColor="#223344")\nremove("shot_1_camera")\n')
    report = n.run_script("mine.py", run_source(src, "mine.py", n))
    assert not report.held
    things = {i["id"]: i for lst in ("items", "materials", "shots") for i in n.data[lst]}
    assert things["sky"]["intensity"] == 0.3 and not things["sky"].get("texture")
    assert things["shot_1"]["camera"] == "cam" and things["ground_material"]["baseColor"] == "#223344"
    assert "shot_1_camera" not in things
    again = n.run_script("mine.py", run_source(src.replace("0.3", "0.5"), "mine.py", n))    # a re-run edits it again
    assert not again.held and next(i for i in n.data["items"] if i["id"] == "sky")["intensity"] == 0.5
