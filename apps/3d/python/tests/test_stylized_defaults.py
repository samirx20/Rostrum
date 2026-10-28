"""The stylized look shows picked colours (no film curve), and a round shape starts smooth enough for an ink outline."""
from rostrum3d import fields as F
from rostrum3d.clay_steps import draw_values
from rostrum3d.engine import STYLIZED_VIEW, _shown


def test_stylized_pictures_skip_the_film_curve(monkeypatch):
    monkeypatch.delenv("OCIO", raising=False)
    assert _shown({"renderer": "stylized"})["view"] == STYLIZED_VIEW
    assert _shown({"renderer": "stylized", "view": "Raw"})["view"] == "Raw"       # asked for: kept
    assert "view" not in _shown({"renderer": "storm"})


def test_round_shapes_start_with_64_steps_boxes_keep_24():
    assert F.defaults("mesh", {"shape": "disc"})["segments"] == 64
    assert F.defaults("mesh", {"shape": "sphere"})["segments"] == 64
    assert F.defaults("mesh", {"shape": "box"})["segments"] == 24


def test_a_drawn_arm_joins_with_half_its_thickness():
    arm = [[0.05 + 0.07 * x, 0.12 + 0.02 * y, 0.0] for x, y in ((-1, 0), (0, -1), (1, 0), (0, 1), (-0.7, 0.7))]
    step = draw_values({"symmetry": "off"}, {"facing": [0, 0, 1]}, arm, 0.0005)
    assert step["blend"] > 0.4 * 0.018                                          # was 0.3 × how fat: a thin crease
