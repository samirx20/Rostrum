"""A drawing layer's Loop: three drawings repeat for the layer's length (looping.py is video's rule too)."""
from rostrum2d import drawing, looping, scene


def layer(loop):
    return {"id": "d", "type": "drawing", "w": 64, "h": 64, "loop": loop, "eachFrame": True,
            "frames": [{"id": f"f{i}", "at": i * 2, "strokes": []} for i in range(3)]}


def test_drawings_repeat_when_loop_is_on_and_hold_when_off():
    d = layer("loop")                                   # drawings at 0, 2, 4; each held 2 frames: a 6-frame cycle
    assert [drawing.frame_at(d, n)["id"] for n in (0, 2, 4, 6, 8, 12)] == ["f0", "f1", "f2", "f0", "f1", "f0"]
    assert [n for n, _ in drawing.repeats(d, 14)][:4] == [0, 2, 4, 6]
    assert drawing.frame_at(layer("off"), 100)["id"] == "f2"
    p = layer("pingpong")                               # the 6 frames' cycle goes there and back
    assert [looping.fold(i, 3, "pingpong") for i in range(6)] == [0, 1, 2, 1, 0, 1]
    assert [drawing.frame_at(p, n)["id"] for n in (5, 7, 9)] == ["f2", "f1", "f0"]
