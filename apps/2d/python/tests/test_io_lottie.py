"""Lottie export: an eased key must land as the right bezier handles (a wrong curve still plays, so it would break
silently), and what Lottie can't carry must be in the report (never dropped silently)."""
from rostrum2d import fields as F
from rostrum2d.io.lottie import to_lottie


def _scene(layer_props=None, anim=None):
    layer = {"id": "box", "type": "shape", "props": {**F.defaults("shape"), **(layer_props or {})}}
    if anim:
        layer["anim"] = anim
    comp = {"id": "c", "type": "comp", "props": {**_sent("comp"), "fps": 30, "duration": 2.0}, "layers": [layer]}
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


def _sent(kind: str) -> dict:
    from rostrum2d.scene import python_only
    return {k: v for k, v in F.defaults(kind).items() if k not in python_only(kind)}


def _tapered():
    layer = {"id": "p", "type": "path", "props": {**_sent("path"), "d": "M 10 50 L 190 50", "w": 200, "h": 100,
                                                   "stroke": True, "strokeWidth": 20, "taperEnd": 1.0}}
    comp = {"id": "c", "type": "comp", "props": {**_sent("comp"), "fps": 30, "duration": 1.0}, "layers": [layer]}
    return {"format": "rostrum-2d-scene", "version": 1, "comp": comp}


def test_a_tapered_stroke_without_the_engine_is_reported_not_dropped(monkeypatch):
    monkeypatch.setenv("ROSTRUM2D_ENGINE", "C:/no/such/engine.exe")
    lottie, report = to_lottie(_tapered())
    assert any("even stroke" in line for line in report)
    assert any(s["ty"] == "st" for s in next(l for l in lottie["layers"] if l["nm"] == "p")["shapes"][0]["it"])


def test_a_tapered_stroke_is_a_filled_outline():              # needs the built engine (ROSTRUM2D_ENGINE)
    import os
    import pytest
    if not os.environ.get("ROSTRUM2D_ENGINE"):
        pytest.skip("ROSTRUM2D_ENGINE not set")
    lottie, report = to_lottie(_tapered())
    items = next(l for l in lottie["layers"] if l["nm"] == "p")["shapes"][0]["it"]
    assert [i["ty"] for i in items if i["ty"] in ("st", "fl")] == ["fl"] and any(i["ty"] == "sh" for i in items), report
