"""The look tools' silent-wrong-answer guards (3d-28): which way a text reads through the camera (mirrored, from behind, upside
down), and unknown shots / materials failing with the known names instead of drawing something else."""
import pytest
from rostrum_core import Document
from rostrum_core.errors import RostrumError

from rostrum3d import KIND, aim, run_source
from rostrum3d.compile import shot_info
from rostrum3d.mcp import material_look, shots_look, text_facts

SCENE = '''
material("gold", baseColor="#ffcc33", metallic=1, roughness=0.2)
cam = camera("cam", focalLength=40, z=3)
mesh("front", shape="text", text="Hello", y=0.3)
mesh("back", shape="text", text="Behind", ry=180, y=0.1)
mesh("upside", shape="text", text="Down", rz=180, y=-0.3)
mesh("tilt", shape="text", text="Tilt", rz=20, x=0.5, y=0.3)
mesh("edge", shape="text", text="Edge", ry=90, x=-0.5)
mesh("away", shape="text", text="Away", x=0.0, z=5)
shot("a", name="Hero 01", camera=cam, fps=24, start=0, end=2)
shot("b", name="Close 02", camera=cam, fps=24, start=0, end=2)
'''


@pytest.fixture(scope="module")
def doc():
    d = Document.new(KIND)
    d.run_script("t.py", run_source(SCENE, "t.py"))
    return d


def reads(doc):
    info = dict(shot_info(doc.data, "a"))
    return {r["item"]: r for r in text_facts.seen_texts(doc, info, 0, 16 / 9)}


def test_text_reading_direction_through_the_shot_camera(doc):
    r = reads(doc)
    assert r["front"]["reads"] == "ok" and r["front"]["angle"] == 0
    assert r["back"]["reads"] == "mirrored" and "from behind" in r["back"]["why"]
    assert r["upside"]["reads"] == "upside-down"
    assert r["tilt"]["reads"] == "tilted" and r["tilt"]["angle"] == pytest.approx(20, abs=0.5)
    assert r["edge"]["reads"] == "edge-on"
    assert "away" not in r                                     # behind the camera: not in the picture, not reported


def test_a_mirrored_copy_with_a_negative_scale_reads_mirrored():
    cam = ([[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 3])
    flipped = ([[-1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 0])
    r = text_facts.reading(flipped, cam)
    assert r["reads"] == "mirrored" and r["scaleFlipped"] and "negative scale" in text_facts._why(r)


def test_look_shots_and_look_material_name_what_exists_for_an_unknown_one(doc):
    ctx = type("C", (), {"tool": "look_shots"})()
    assert shots_look.chosen(ctx, doc, ["hero 01", "b"]) == ["a", "b"]           # a name (any case) or an id
    with pytest.raises(RostrumError) as e:
        shots_look.chosen(ctx, doc, ["Hero 01", "Wide 03"])
    assert "Wide 03" in str(e.value) and "Close 02" in str(e.value)
    with pytest.raises(RostrumError) as e:
        material_look.find(ctx, doc, "silver")
    assert "gold" in str(e.value)
