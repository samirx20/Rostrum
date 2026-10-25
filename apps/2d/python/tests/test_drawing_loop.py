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


def test_a_cycle_plays_its_times_then_holds_and_steps_on_each_repeat():
    from rostrum2d import drawing_loop
    d = {**layer("loop"), "loopTimes": 2, "loopStepX": 30.0}       # a 6-frame cycle, twice, 30 canvas px further each time
    assert [drawing.frame_at(d, n)["id"] for n in (0, 6, 8, 11, 12, 40)] == ["f0", "f0", "f1", "f2", "f2", "f2"]
    node = {"props": {"anchorX": 0.5, "anchorY": 0.5}}
    drawing_loop.step(node, d, drawing.cycle(d), (64, 64), 24, 2.0)
    assert [(k["t"] * 24, k["v"]) for k in node["anim"]["anchorX"]] == [(0, 0.5), (6, 0.5 - 30 / 64)]    # one step, then held
