"""An agent's script that remakes or edits the new scene's ground, sky and camera owns them: nothing is "held back … already
changed by script:start.py" (the agent then believed its sky edits were dropped), while a person's own edit still is."""
from rostrum_core import Document, Who

from rostrum3d import KIND, run_source
from rostrum3d.start_scene import SOURCE

AGENT, SAM = Who.agent("claude"), Who.person()
A = ('material("ground_material", baseColor="#223344")\nedit("ground", width=50)\nlight("sky", kind="dome", exposure=-1)\n'
     'edit("shot_1_camera", focalLength=70)\nmesh("b", shape="box")\n')


def _start(tmp_path):
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("start.py", run_source(SOURCE, "start.py"))
    return d


def test_the_starter_floor_sky_and_camera_are_the_agents_own_to_change(tmp_path):
    d = _start(tmp_path)
    for src in (A, A.replace("-1", "-2").replace("50", "60").replace("70", "60")):
        report = d.run_script("scene.py", run_source(src, "scene.py", d), AGENT)
        assert report.held == []
    assert (d.item("sky")["exposure"], d.item("ground")["width"], d.item("shot_1_camera")["focalLength"]) == (-2, 60, 60)


def test_a_persons_edit_of_the_starter_sky_is_still_held_back(tmp_path):
    d = _start(tmp_path)
    d.apply({"op": "light.set", "target": ["sky"], "args": {"exposure": 0.5}}, SAM)
    report = d.run_script("scene.py", run_source(A, "scene.py", d), AGENT)
    assert d.item("sky")["exposure"] == 0.5 and any(h["key"].startswith("sky") for h in report.held)
