"""Product lighting (H21): a strip reaches the core as the right props, and linking to a missing item fails loudly
(a light silently lighting everything would look like a renderer bug)."""
import pytest
from rostrum_core import Document

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
