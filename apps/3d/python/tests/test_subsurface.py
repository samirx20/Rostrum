"""Light under the surface (CL6): what would break silently. Every start is a valid material; the compiled scene
carries a material's subsurface values to the core (colour linear, distance in mm); a new clay starts with the
project's shared "Clay" material, made once, in the same undo step."""
import pytest
from rostrum_core import Document, Who

from rostrum3d import KIND, compile as C
from rostrum3d.material_starts import STARTS, start_key

SAM = Who.person()


@pytest.mark.parametrize("key", list(STARTS))
def test_every_start_makes_a_valid_material(key):
    d = Document.new(KIND)
    d.apply({"op": "material.from", "args": {"start": key, "id": "m"}}, SAM)
    assert not KIND.check(d.data)
    assert start_key(STARTS[key]["label"]) == key


def test_the_scene_carries_subsurface_to_the_core():
    d = Document.new(KIND)
    d.apply([{"op": "material.from", "args": {"start": "skin", "id": "skin"}},
             {"op": "mesh.add", "args": {"id": "ear", "shape": "sphere", "material": "skin"}},
             {"op": "camera.add", "args": {"id": "cam", "z": 2}},
             {"op": "shot.add", "args": {"id": "hero", "camera": "cam", "start": 0, "end": 1}}], SAM)
    props = next(m for m in C.describe(d.data, "hero")["materials"] if m["id"] == "skin")["props"]
    assert props["subsurface"] == 1 and props["subsurfaceRadius"] == pytest.approx(3.7)
    r, g, b = props["subsurfaceColor"]                       # #ffa477 in linear: red travels farthest
    assert r == pytest.approx(1.0) and g == pytest.approx(0.371, abs=0.01) and b == pytest.approx(0.184, abs=0.01)


def test_new_clays_share_the_clay_material_and_undo_takes_it_back():
    d = Document.new(KIND)
    d.apply({"op": "clay.add", "args": {"id": "a", "at": [0, 0, 0], "radius": 0.1}}, SAM)
    mats = d.data["materials"]
    assert len(mats) == 1 and mats[0]["name"] == "Clay" and d.item("a")["material"] == mats[0]["id"]
    assert mats[0]["roughness"] == STARTS["clay"]["values"]["roughness"]
    d.apply({"op": "clay.add", "args": {"id": "b", "at": [1, 0, 0], "radius": 0.1}}, SAM)
    assert len(d.data["materials"]) == 1 and d.item("b")["material"] == mats[0]["id"]
    d.undo(SAM)
    d.undo(SAM)
    assert d.data["materials"] == []
