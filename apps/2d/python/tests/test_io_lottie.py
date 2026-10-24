"""Lottie export: an eased key must land as the right bezier handles (a wrong curve still plays, so it would break
silently), and what Lottie can't carry must be in the report (never dropped silently)."""
from rostrum2d import fields as F
from rostrum2d.io.lottie import to_lottie


def _scene(layer_props=None, anim=None):
    layer = {"id": "box", "type": "shape", "props": {**F.defaults("shape"), **(layer_props or {})}}
    if anim:
        layer["anim"] = anim
    comp = {"id": "c", "type": "comp", "props": {**_sent("comp"), "fps": 30, "duration": 2.0}, "layers": [layer]}
    from rostrum2d.scene import FORMAT, VERSION
    return {"format": FORMAT, "version": VERSION, "comp": comp}


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
    from rostrum2d.scene import _engine_props
    return _engine_props(kind, {})


def _tapered():
    layer = {"id": "p", "type": "path", "props": {**_sent("path"), "d": "M 10 50 L 190 50", "w": 200, "h": 100,
                                                   "stroke": True, "strokeWidth": 20, "taperEnd": 1.0}}
    comp = {"id": "c", "type": "comp", "props": {**_sent("comp"), "fps": 30, "duration": 1.0}, "layers": [layer]}
    from rostrum2d.scene import FORMAT, VERSION
    return {"format": FORMAT, "version": VERSION, "comp": comp}


def test_a_tapered_stroke_without_the_engine_is_reported_not_dropped(monkeypatch):
    monkeypatch.setenv("ROSTRUM2D_ENGINE", "C:/no/such/engine.exe")
    lottie, report = to_lottie(_tapered())
    assert any("even stroke" in line for line in report)
    assert any(s["ty"] == "st" for s in next(l for l in lottie["layers"] if l["nm"] == "p")["shapes"][0]["it"])


def test_a_tapered_stroke_is_a_filled_outline():              # needs the built engine
    import pytest
    from rostrum2d import settings
    if reason := settings.engine_missing_reason():
        pytest.skip(reason)
    lottie, report = to_lottie(_tapered())
    items = next(l for l in lottie["layers"] if l["nm"] == "p")["shapes"][0]["it"]
    assert [i["ty"] for i in items if i["ty"] in ("st", "fl")] == ["fl"] and any(i["ty"] == "sh" for i in items), report


def test_a_frame_move_is_baked_where_the_engine_puts_the_layers():
    # S27 H3: a camera failed the export. Baked, each layer must land where frame/view.py (the engine's maths) puts it.
    import math
    from rostrum2d.frame.view import Shot, layer_matrix
    sc = _scene({"depth": 1.0})
    cam = {"id": "frame", "type": "camera", "props": {**_sent("camera"), "x": 960, "y": 540, "homeX": 960, "homeY": 540},
           "anim": {"x": [{"t": 0, "v": 960}, {"t": 2, "v": 1360}], "zoom": [{"t": 0, "v": 1.0}, {"t": 2, "v": 1.5}],
                    "rotation": [{"t": 0, "v": 0}, {"t": 2, "v": 10}]}}
    sc["comp"]["layers"].insert(0, cam)
    baked = []
    lottie, report = to_lottie(sc, baked=baked)
    box = next(l for l in lottie["layers"] if l["nm"] == "box")
    null = next(l for l in lottie["layers"] if l["ind"] == box["parent"])
    f = 45
    a, s, r = (next(k["s"] for k in null["ks"][n]["k"] if k["t"] == f) for n in ("a", "s", "r"))
    t, (px, py) = f / 30, (100.0, 200.0)
    cam_now = Shot(960 + 400 * _ease_frac(sc, "x", t), 540, 1 + 0.5 * _ease_frac(sc, "zoom", t), 10 * _ease_frac(sc, "rotation", t), 960, 540)
    m = layer_matrix(sc["comp"]["props"], cam_now, {"depth": 1.0})
    want = (m[0] * px + m[2] * py + m[4], m[1] * px + m[3] * py + m[5])
    z, rad = s[0] / 100, math.radians(r[0])
    qx, qy = px - a[0], py - a[1]
    got = (960 + z * (math.cos(rad) * qx - math.sin(rad) * qy), 540 + z * (math.sin(rad) * qx + math.cos(rad) * qy))
    assert math.dist(got, want) < 0.01
    assert not report and any("frame" in line for line in baked)        # carried exactly: not a difference


def _ease_frac(sc, name, t):
    from rostrum_core.keys import track_value
    keys = sc["comp"]["layers"][0]["anim"][name]
    return (track_value(keys, t) - keys[0]["v"]) / (keys[1]["v"] - keys[0]["v"])


def _fill_o(lottie):
    layer = next(l for l in lottie["layers"] if l["nm"] == "box")
    fill = next(g for g in layer["shapes"] if g["nm"] == "fill")
    return next(i for i in fill["it"] if i["ty"] == "fl")["o"]


def test_a_fill_opacity_goes_to_the_fill_and_an_old_file_stays_full():
    still, _ = to_lottie(_scene({"fillOpacity": 0.4}))
    assert _fill_o(still) == {"a": 0, "k": 40.0}
    keyed, _ = to_lottie(_scene(anim={"fillOpacity": [{"t": 0.0, "v": 1.0}, {"t": 1.0, "v": 0.2}]}))
    first, last = _fill_o(keyed)["k"]
    assert (first["s"], last["s"]) == ([100], [20.0])
    old = _scene()
    del old["comp"]["layers"][0]["props"]["fillOpacity"]
    assert _fill_o(to_lottie(old)[0]) == {"a": 0, "k": 100.0}
