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


def _start(tmp_path):
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("start.py", run_source(SOURCE, "start.py"))
    return d


def test_the_first_picture_is_a_floor_under_a_thin_band_of_sky(tmp_path):
    """The horizon sits in the top 15–25 % of the shot's frame, and a 30 cm figure at the middle fills about half its
    height (the shot's 16:9 frame, the camera's sensor width and focal length)."""
    d = _start(tmp_path)
    scene = describe(d.data, "shot_1")
    props = next(n for n in scene["items"] if n["id"] == "shot_1_camera")["props"]
    shot = d.data["shots"][0]
    w, h = shot.get("width", 1920), shot.get("height", 1080)
    half = props["sensorWidth"] * h / w / 2 / props["focalLength"]       # tan of half the frame's height
    cam = _Frames(d.data, range(0, 1), 24).world("shot_1_camera", 0)
    eye = aim.point(cam, [0, 0, 0])
    fwd = [a - e for a, e in zip(aim.point(cam, [0, 0, -1]), eye)]
    up = [a - e for a, e in zip(aim.point(cam, [0, 1, 0]), eye)]

    def down_from_top(p):                                                 # 0 = the frame's top edge, 1 = its bottom
        v = [a - e for a, e in zip(p, eye)]
        y = sum(a * b for a, b in zip(v, up)) / sum(a * b for a, b in zip(v, fwd))
        return 0.5 - y / half / 2

    horizon = down_from_top([eye[0] + fwd[0] * 1e4, eye[1], eye[2] + fwd[2] * 1e4])
    assert 0.15 <= horizon <= 0.25
    figure = down_from_top([0, 0, 0]) - down_from_top([0, 0.3, 0])
    assert 0.4 <= figure <= 0.6


def test_the_ground_is_a_backdrop_the_engine_never_hears_of(tmp_path):
    d = _start(tmp_path)
    assert d.item("ground")["backdrop"] is True
    ground = next(n for n in describe(d.data, "shot_1")["items"] if n["id"] == "ground")
    assert "backdrop" not in ground["props"]
