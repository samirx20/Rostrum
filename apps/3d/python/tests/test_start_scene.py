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
    assert set(by_id) == {"ground", "sky", "key_light", "rim_light", "shot_1_camera"} and d.data["shots"][0]["name"] == "Shot 1"
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


def test_the_first_picture_is_all_floor_with_no_horizon(tmp_path):
    """The horizon is above the shot's frame (no photographed room across its top), and a 30 cm figure at the middle fills about half its
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
    assert horizon < -0.05
    figure = down_from_top([0, 0, 0]) - down_from_top([0, 0.3, 0])
    assert 0.4 <= figure <= 0.6


def test_the_ground_is_a_backdrop_the_engine_never_hears_of(tmp_path):
    d = _start(tmp_path)
    assert d.item("ground")["backdrop"] is True
    ground = next(n for n in describe(d.data, "shot_1")["items"] if n["id"] == "ground")
    assert "backdrop" not in ground["props"]


def test_guide_reaches_the_engine_only_when_on(tmp_path):
    """`guide` is read only where a mesh is drawn; sent off it broke every combine's inputs (the engine refused the
    scene: 'bowl_outer.guide: unknown field')."""
    d = _start(tmp_path)
    ground = next(n for n in describe(d.data, "shot_1")["items"] if n["id"] == "ground")
    assert "guide" not in ground["props"]


def _ids(d):
    return {n["id"] for n in d.data["items"]}


def _run(d, src, name="mine.py"):
    return d.run_script(name, run_source(src, name, d))


def test_a_script_without_lights_keeps_the_start_sky_and_lights(tmp_path):
    d = _start(tmp_path)
    _run(d, 'mesh("cube", shape="box", y=0.1)')
    assert {"ground", "sky", "key_light", "rim_light", "cube"} <= _ids(d)


def test_a_dome_replaces_the_sky_a_panel_adds_to_the_start_panels_unless_it_replaces_them(tmp_path):
    d = _start(tmp_path)
    _run(d, 'light("dusk", kind="dome", color="#334466")')
    assert "sky" not in _ids(d) and {"dusk", "key_light", "rim_light"} <= _ids(d)       # a dome: only the sky goes
    _run(d, 'light("dusk", kind="dome", color="#334466")\nlight("softbox", kind="rect", x=1, y=1, z=1)')
    assert {"dusk", "softbox", "key_light", "rim_light"} <= _ids(d)                    # a panel of its own: added
    report = _run(d, 'light("dusk", kind="dome", color="#334466")\n'
                     'light("softbox", kind="rect", x=1, y=1, z=1, replace_start_lights=True)')
    assert "key_light" not in _ids(d) and "rim_light" not in _ids(d) and {"dusk", "softbox"} <= _ids(d)
    assert "key_light" in report.summary() and "rim_light" in report.summary()       # the reply names what went
    _run(d, 'light("dusk", kind="dome", color="#334466")\n'
            'light("softbox", kind="rect", x=1, y=1, z=1, replace_start_lights=True)')   # a re-run changes nothing
    assert _ids(d) >= {"dusk", "softbox", "ground"} and not {"sky", "key_light"} & _ids(d)


def test_making_the_sky_again_or_editing_it_keeps_the_other_start_lights(tmp_path):
    d = _start(tmp_path)
    _run(d, 'edit("sky", intensity=0.4)')
    assert {"sky", "key_light", "rim_light"} <= _ids(d) and d.item("sky")["intensity"] == 0.4
    _run(d, 'light("sky", kind="dome", intensity=0.4)', "again.py")
    assert {"sky", "key_light", "rim_light"} <= _ids(d)


def test_the_start_sky_lights_but_is_not_seen_so_a_low_camera_sees_a_plain_horizon(tmp_path):
    """Drape (round 5): a low camera saw the Studio photo's room (a black band, a grey panel) above the floor."""
    d = _start(tmp_path)
    assert d.item("sky")["seenByCamera"] is False and d.item("sky")["texture"] == "sky:studio"
    from rostrum3d.start_scene import HORIZON
    assert d.data["shots"][0]["background"] == HORIZON != "#000000"


def test_a_fabric_made_in_a_colour_shines_in_that_colour():
    """Drape (round 5): a white sheen turned flat red cloth pale pink-white like paper."""
    from rostrum3d.material_starts import start_values
    assert start_values("fabric", {"baseColor": "#b3262e"})["sheenTint"] == "#b3262e"
    assert start_values("fabric", {"baseColor": "#b3262e", "sheenTint": "#ffffff"})["sheenTint"] == "#ffffff"
