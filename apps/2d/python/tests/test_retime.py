"""A layer timed from a shared marker moves with the marker, children and all; a missing marker fails loudly (retime.py)."""
import pytest
from rostrum_core import RostrumError

from rostrum2d import retime


def _comp():
    title = {"id": "title", "type": "text", "start": 0.2, "keys": [{"prop": "opacity", "t": 0.0, "v": 0}, {"prop": "opacity", "t": 0.5, "v": 1}],
             "effects": [{"id": "glow", "type": "glow", "keys": [{"prop": "radius", "t": 0.5, "v": 9}]}]}
    own = {"id": "own", "type": "shape", "marker": "drop", "keys": [{"prop": "x", "t": 0.1, "v": 1}]}
    shot = {"id": "shot", "type": "group", "marker": "reveal", "end": 3.0, "layers": [title, own]}
    return {"id": "main", "type": "comp", "fps": 30, "layers": [shot, {"id": "bg", "type": "shape", "keys": [{"prop": "x", "t": 1.0, "v": 0}]}]}


def test_layers_follow_their_marker():
    comp = _comp()
    out = retime.timed(comp, {"reveal": 10.0, "drop": 12.0}, 30)
    shot, bg = out["layers"]
    title, own = shot["layers"]
    assert (shot["start"], shot["end"]) == (10.0, 13.0)
    assert title["start"] == pytest.approx(10.2) and [k["t"] for k in title["keys"]] == [10.0, 10.5]
    assert title["effects"][0]["keys"][0]["t"] == 10.5                     # an effect's keys go with its layer
    assert own["keys"][0]["t"] == pytest.approx(12.1) and own["start"] == 12.0  # its own marker wins
    assert bg["keys"][0]["t"] == 1.0                                         # untimed layers stay put
    assert comp["layers"][0]["layers"][0]["keys"][0]["t"] == 0.0             # the document keeps times from the marker
    moved = retime.timed(comp, {"reveal": 11.0, "drop": 12.0}, 30)
    assert moved["layers"][0]["layers"][0]["keys"][1]["t"] == 11.5


def test_missing_marker_fails_loudly():
    with pytest.raises(RostrumError, match='marker "drop"'):
        retime.timed(_comp(), {"reveal": 1.0}, 30)


def test_ends_on_a_marker_and_the_frame_cuts_on_markers():
    cut = [{"id": "frame.x.k_reveal_m33", "prop": "x", "t": "#reveal-0.033", "v": 960, "ease": "hold"},
           {"id": "frame.x.k_reveal", "prop": "x", "t": "#reveal", "v": 2900}]
    comp = {"id": "main", "type": "comp", "layers": [{"id": "frame", "type": "camera", "keys": cut},
                                                     {"id": "phone", "type": "group", "marker": "ui", "start": -0.2, "endMarker": "reveal"}]}
    out = retime.timed(comp, {"ui": 6.4, "reveal": 11.6, "end": 20.0}, 30)
    frame, phone = out["layers"]
    assert (phone["start"], phone["end"]) == (pytest.approx(6.2), pytest.approx(11.6))   # a lead-in, and gone on reveal
    assert [k["t"] for k in frame["keys"]] == [pytest.approx(11.567), 11.6] and "start" not in frame
    moved = retime.timed(comp, {"ui": 6.4, "reveal": 11.9, "end": 20.0}, 30)
    assert moved["layers"][1]["end"] == pytest.approx(11.9) and moved["layers"][0]["keys"][1]["t"] == 11.9


def test_diagnose_lists_every_missing_marker_instead_of_failing():
    """P20 friction 9: a key on a missing marker made inspect_diagnose crash; it now lists each one by name."""
    from rostrum2d import diagnose
    comp = _comp()
    comp["layers"][1]["keys"].append({"id": "bg.x.k_logo_m150", "prop": "x", "t": "#logo-0.15", "v": 3})
    found = [p["item"] for p in diagnose.problems(comp, None, {"reveal": 1.0}) if p["kind"] == "missing-marker"]
    assert sorted(found) == ["bg.x.k_logo_m150", "own"]
