"""Ground first, place by relation, frame by subject, and start things kept (script_ground / script_place / script_shot):
what agents rely on so they never write y = h/2, guess metres, or lose the start lights or shot_1's camera."""
import pytest

from rostrum_core import Document
from rostrum_core.errors import RostrumError

from rostrum3d import KIND, aim, item_bounds, ops_shot_camera as SC, run_source
from rostrum3d.resolve import Frames
from rostrum3d.start_scene import SOURCE


def _start(tmp_path):
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("start.py", run_source(SOURCE, "start.py"))
    return d


def _run(d, src, name="mine.py"):
    return d.run_script(name, run_source(src, name, d))


def _box(d, id_):
    return item_bounds.world_box(d.data, [id_], 0.0)


def test_a_mesh_and_a_group_stand_on_the_ground_y_is_the_base_height(tmp_path):
    d = _start(tmp_path)
    _run(d, 'mesh("cube", shape="box", width=0.2, height=0.2, depth=0.2)\n'
            'mesh("tilt", shape="box", width=0.2, height=0.2, depth=0.2, rz=45, x=1, y=0.3)\n'
            'mesh("float", shape="sphere", radius=0.1, y_world=1)\n'
            'with group("g", x=-1):\n    mesh("leg", shape="box", width=0.1, height=0.5, depth=0.1)\n')
    assert abs(_box(d, "cube")[0][1]) < 1e-9 and abs(_box(d, "g")[0][1]) < 1e-9          # on the ground
    assert abs(_box(d, "tilt")[0][1] - 0.3) < 1e-6                                         # turned: its corner 30 cm up
    assert d.item("float")["y"] == 1


def test_row_lays_things_side_by_side_centred_and_on_the_ground(tmp_path):
    d = _start(tmp_path)
    _run(d, 'a = mesh("a", shape="box", width=0.1, height=0.3, depth=0.1, y=0.5)\n'
            'b = mesh("b", shape="sphere", radius=0.05)\n'
            'mesh("c", shape="cylinder", radius=0.08, height=0.1)\n'
            'row([a, b, "c"], gap=0.05)')
    (alo, ahi), (blo, bhi), (clo, chi) = (_box(d, i) for i in "abc")
    assert abs(blo[0] - ahi[0] - 0.05) < 1e-6 and abs(clo[0] - bhi[0] - 0.05) < 1e-6
    assert abs(alo[0] + chi[0]) < 1e-6 and all(abs(lo[1]) < 1e-6 for lo in (alo, blo, clo))


def test_shot_frames_its_subject_at_the_left_third_and_keeps_its_camera(tmp_path):
    d = _start(tmp_path)
    _run(d, 'mesh("cube", shape="box", width=0.2, height=0.2, depth=0.2)\n'
            'shot("shot_1", end=3, frame="cube", at=(1/3, 0.5), fill=0.5)')
    shot = d.data["shots"][0]
    assert shot["camera"] == "shot_1_camera" and shot["end"] == 3                 # made again: its camera kept
    eye, (right, up, fwd), tan_w, tan_h, _ = SC.view(Frames(d.data, range(0, 1), 1.0), "shot_1_camera", 0, shot)
    rel = [m - e for m, e in zip([0, 0.1, 0], eye)]
    depth = sum(a * b for a, b in zip(rel, fwd))
    x = (1 + sum(a * b for a, b in zip(rel, right)) / (depth * tan_w)) / 2
    y = (1 - sum(a * b for a, b in zip(rel, up)) / (depth * tan_h)) / 2
    tall = [sum(a * b for a, b in zip(c, up)) for c in item_bounds._corners(*_box(d, "cube"))]   # as seen, tilted
    assert abs(x - 1 / 3) < 1e-4 and abs(y - 0.5) < 1e-4 and abs((max(tall) - min(tall)) / (2 * depth * tan_h) - 0.5) < 1e-3


def test_a_shot_with_no_camera_is_seen_through_the_default_view_and_says_so(tmp_path):
    tree = run_source('shot("s", end=2)', "t.py")
    assert tree["shots"][0]["camera"] == "s_camera" and any(i["id"] == "s_camera" and i["type"] == "camera" for i in tree["items"])
    assert any('shot "s" has no camera: it is seen through the default view' in n for n in tree.notes)
    d = _start(tmp_path)                                                  # the new scene's shot_1_camera is used, not doubled
    src = 'shot("shot_1", end=3)\nshot("shot_2", end=2)'
    tree = run_source(src, "mine.py", d)
    assert [s.get("camera") for s in tree["shots"]] == ["shot_1_camera", "shot_2_camera"]
    assert not any(i["id"] == "shot_1_camera" for i in tree["items"])        # shot_1 keeps the start camera
    _run(d, src)
    assert d.item("shot_2")["camera"] == "shot_2_camera" and d.item("shot_2_camera")["type"] == "camera"


def test_a_light_of_its_own_keeps_the_start_lights(tmp_path):
    d = _start(tmp_path)
    _run(d, 'light("key", kind="rect", x=1, y=1, z=1, brightness=0).aim((0, 0.1, 0))')
    ids = {i["id"] for i in d.data["items"]}
    assert {"key", "key_light", "rim_light", "sky"} <= ids
    key = d.item("key")
    assert key["normalize"] and key["exposure"] == 0 and 10 < key["intensity"] < 20      # ~ the start key at ~1.7 m
