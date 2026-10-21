"""The camera maths (camera/view.py) the look tools use must match CAMERA.md's (and the engine's): hand-computed points."""
from rostrum2d.camera.view import layer_matrix, undo

COMP = {"width": 1920, "height": 1080}


def at(m, x, y):
    return (round(m[0] * x + m[2] * y + m[4], 6), round(m[1] * x + m[3] * y + m[5], 6))


def test_rest_shows_every_layer_as_placed():
    assert at(layer_matrix(COMP, (960, 540, 1, 0), {"depth": 3.0}), 123, 45) == (123, 45)


def test_far_layer_pans_and_zooms_less_and_roll_turns_the_picture_back():
    # depth 1: s = 1/2, zoom 4 → 2, the camera 200 px right → 100 px for this layer.
    assert at(layer_matrix(COMP, (1160, 540, 4, 0), {"depth": 1.0}), 910, 490) == (660, 440)
    # The camera rolls 90° clockwise: a point 100 px above where it looks shows 100 px left of the centre.
    m = layer_matrix(COMP, (1060, 540, 1, 90), {"depth": 0.0})
    assert at(m, 1060, 440) == (860, 540)
    assert tuple(round(v, 6) for v in undo(m, 860, 540)) == (1060, 440)
    assert layer_matrix(COMP, (1060, 540, 1, 90), {"screenLock": True}) == (1, 0, 0, 1, 0, 0)
