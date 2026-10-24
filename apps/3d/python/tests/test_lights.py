"""Product lighting (H21): a strip reaches the core as the right props, and linking to a missing item fails loudly
(a light silently lighting everything would look like a renderer bug)."""
import pytest
from rostrum_core import Document, Who

from rostrum3d import KIND, run_source
from rostrum3d.compile import describe

BASE = '''
mesh("bottle", shape="cylinder", radius=0.04, height=0.2)
cam = camera("cam", z=1)
shot("hero", camera=cam, fps=24, start=0, end=1)
'''


def scene_of(extra: str) -> dict:
    d = Document.new(KIND)
    d.run_script("lights.py", run_source(BASE + extra, "lights.py"))
    return {n["id"]: n for n in describe(d.data, "hero")["items"]}


def test_strip_compiles_to_its_scene_props():
    items = scene_of('light("rim", kind="strip", length=1.5, width=0.12, spread=40, card=True, lightsOnly="bottle")\n'
                     'light("sky", kind="dome", turn=90, seenByCamera=False)\n')
    rim, sky = items["rim"]["props"], items["sky"]["props"]
    assert (rim["kind"], rim["length"], rim["width"], rim["spread"], rim["card"], rim["lightsOnly"]) == \
        ("strip", 1.5, 0.12, 40.0, True, "bottle")
    assert (sky["rx"], sky["ry"], sky["rz"], sky["seenByCamera"]) == (0.0, 90.0, 0.0, False) and "turn" not in sky


def test_linking_to_a_missing_item_fails_loudly():
    with pytest.raises(Exception, match='lightsOnly: no item "bottel"'):
        scene_of('light("rim", kind="strip", lightsOnly="bottle bottel")\n')


def test_spot_starts_as_a_small_bulb_and_its_cone_animates():
    spot = scene_of('light("pool", kind="spot", softness=0.4).key("cone", {0: 30, 1: 60})\n')["pool"]
    assert (spot["props"]["kind"], spot["props"]["radius"], spot["props"]["softness"]) == ("spot", 0.05, 0.4)
    assert spot["anim"]["cone"][0] == 30 and len(set(spot["anim"]["cone"])) > 1


def test_place_highlight_mirrors_the_view_and_starts_at_a_sensible_brightness():
    d = Document.new(KIND)
    d.run_script("lights.py", run_source(BASE, "lights.py"))
    d.apply([{"op": "light.add", "args": {"id": "key", "kind": "rect", "width": 0.5, "height": 0.5}}], Who.person())
    d.apply([{"op": "light.place_highlight", "target": ["key"], "args": {
        "point": [0, 0, 0], "normal": [0, 1, 0], "eye": [0, 1, 1], "distance": 2, "brightness": True}}], Who.person())
    key = d.item("key")
    s = 2 ** -0.5                                          # the view ray (0, -1, -1) bounces to (0, 1, -1)
    assert [round(key[k], 4) for k in "xyz"] == [0, round(2 * s, 4), round(-2 * s, 4)]
    assert (key["aim"], key["aimY"], key["intensity"]) == ("point", 0, 3.0 * 4 / 0.25)
