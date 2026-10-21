"""Lottie export: an eased key must land as the right bezier handles (a wrong curve still plays, so it would break
silently), and what Lottie can't carry must be in the report (never dropped silently)."""
from rostrum2d import fields as F
from rostrum2d.io.lottie import to_lottie


def _scene(layer_props=None, anim=None):
    layer = {"id": "box", "type": "shape", "props": {**F.defaults("shape"), **(layer_props or {})}}
    if anim:
        layer["anim"] = anim
    comp = {"id": "c", "type": "comp", "props": {**F.defaults("comp"), "fps": 30, "duration": 2.0}, "layers": [layer]}
    return {"format": "rostrum-2d-scene", "version": 1, "comp": comp}


def test_an_eased_key_becomes_its_bezier_handles():
    keys = [{"t": 0.5, "v": 100, "ease": "snappy"}, {"t": 1.5, "v": 300}]
    lottie, _ = to_lottie(_scene(anim={"x": keys}))
    layer = next(l for l in lottie["layers"] if l["nm"] == "box")
    first, last = layer["ks"]["p"]["x"]["k"]
    assert (first["t"], last["t"]) == (15, 45)                       # seconds → frames
    assert (first["o"]["x"][0], first["o"]["y"][0], first["i"]["x"][0], first["i"]["y"][0]) == (0.16, 1.0, 0.3, 1.0)
    assert first["s"] == [100] and last["s"] == [300]


def test_a_tilted_layer_is_reported():
    _, report = to_lottie(_scene({"tiltX": 25}))
    assert any('"box"' in line and "tilt" in line for line in report)
