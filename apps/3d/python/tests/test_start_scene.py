"""A new scene (start_scene.py, SPEC §1 "Before the first click"): what breaks silently is a new project the engine can't
build (a sky file that isn't there, a shot without a camera) or a camera that doesn't look at the ground's middle."""
from pathlib import Path

from rostrum_core import Document

from rostrum3d import KIND, aim, run_source, skies
from rostrum3d.compile import _Frames, describe
from rostrum3d.start_scene import SOURCE


def test_a_new_scene_is_a_ground_the_studio_sky_and_shot_1_looking_at_the_middle(tmp_path):
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("start.py", run_source(SOURCE, "start.py"))
    scene = describe(d.data, "shot_1")
    by_id = {n["id"]: n for n in scene["items"]}
    assert set(by_id) == {"ground", "sky", "shot_1_camera"} and d.data["shots"][0]["name"] == "Shot 1"
    sky = Path(by_id["sky"]["props"]["texture"])
    assert sky.is_file() and sky.read_bytes()[:10] == b"#?RADIANCE"       # the file that comes with the app, absolute
    cam = _Frames(d.data, range(0, 1), 24).world("shot_1_camera", 0)
    eye, ahead = aim.point(cam, [0, 0, 0]), aim.point(cam, [0, 0, -1])
    t = eye[2] / (eye[2] - ahead[2])                                      # where its middle ray passes z = 0
    over = [e + (a - e) * t for e, a in zip(eye, ahead)]
    assert abs(over[0]) < 1e-6 and 0 <= over[1] < 0.5                      # just above the ground's middle
    assert skies.label("sky:studio") == "Studio" and skies.choices("")[-1]["label"] == "Plain colour"
