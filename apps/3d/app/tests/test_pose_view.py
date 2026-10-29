"""The pose overlay (pose_view.py) draws the pose you see: with an animation layer posing a bone, the bone lines follow
the layer, as the picture does (skin.transforms with the document's layer stack). Drawn from the Base, the lines sat off
the clay and nothing failed. No Qt, no engine."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum3d import aim, skin  # noqa: E402
from screen3d import pose_view as PV  # noqa: E402

LAYER = {"id": "wave", "type": "animLayer", "name": "Wave", "weight": 1.0, "mode": "add", "on": True}
CLAY = {"id": "c", "bones": [{"id": "upper", "length": 1.0, "bones": [
    {"id": "lower", "y": 1.0, "length": 1.0, "keys": [{"prop": "rz", "t": 0.0, "v": 90.0, "layer": "wave"}]}]}]}


class Flat:
    """A view that keeps x and y (picture px = world units)."""

    @staticmethod
    def project(p):
        return [p[0], p[1], 1.0]


def test_the_bone_lines_follow_an_animation_layer():
    world = aim.local({"x": 0, "y": 0, "z": 0, "rx": 0, "ry": 0, "rz": 0, "sx": 1, "sy": 1, "sz": 1})
    drawn = PV.overlay(CLAY, [], world, Flat, 0.5, [LAYER], 1.0, 1.0)
    tip = drawn["lines"][1]["b"]
    seen = skin.transforms(skin.bones_of(CLAY), 0.5, [LAYER])[1]
    assert tip == pytest.approx(skin.segment(seen, CLAY["bones"][0]["bones"][0])[3:5])
    assert tip != pytest.approx([0.0, 2.0])                    # the Base would keep the lower bone straight up


def test_a_time_without_the_layers_is_an_error():
    with pytest.raises(TypeError):
        skin.transforms(skin.bones_of(CLAY), 0.5)
