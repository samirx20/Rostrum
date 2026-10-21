"""Keys timed on a shared marker ("#drop+0.2", rostrum_core.keys.marked): they land on the marker wherever their layer
counts from, before the layer's start too (pre-roll); moving the marker moves them; a marker that is gone fails
loudly naming the key; key.add writes them and a drag keeps them on their marker."""
import pytest
from rostrum_core import Document, RostrumError, Who
from rostrum_core.keys import marked

from rostrum2d import KIND, retime


def _comp():
    flash = {"id": "flash", "type": "shape", "marker": "reveal", "start": 0.0, "keys": [
        {"id": "a", "prop": "opacity", "t": 0.5, "v": 0},
        {"id": "b", "prop": "opacity", "t": "#drop-0.5", "v": 0.2},       # a pre-roll into the drop
        {"id": "c", "prop": "opacity", "t": "#drop+0.2", "v": 1}]}
    return {"id": "main", "type": "comp", "fps": 30, "layers": [flash]}


def test_marker_keys_follow_their_marker_and_fail_loudly():
    comp = _comp()
    keys = retime.timed(comp, {"reveal": 10.0, "drop": 12.0}, 30)["layers"][0]["keys"]
    assert [k["t"] for k in keys] == [10.5, 11.5, pytest.approx(12.2)]    # own marker, not the layer's
    moved = retime.timed(comp, {"reveal": 10.0, "drop": 13.0}, 30)["layers"][0]["keys"]
    assert [k["t"] for k in moved] == [10.5, 12.5, pytest.approx(13.2)]
    early = retime.timed(comp, {"reveal": 10.0, "drop": 10.2}, 30)["layers"][0]["keys"]
    assert early[1]["t"] == pytest.approx(9.7)                             # before the layer's start: kept
    placed = retime.placed(comp, {"reveal": 10.0, "drop": 12.0})["layers"][0]["keys"]
    assert placed[2]["t"] == pytest.approx(2.2) and marked.label(placed[2]["ref"]) == "drop +0.2 s"
    assert comp["layers"][0]["keys"][2]["t"] == "#drop+0.2"               # the document keeps what was written
    with pytest.raises(RostrumError) as err:
        retime.timed(comp, {"reveal": 10.0}, 30)
    assert err.value.where == "b" and "drop" in str(err.value.to_dict())


def test_key_add_on_a_marker_and_a_drag_keeps_it_there():
    d = Document.new(KIND)
    sam = Who.person("sam")
    d.apply([{"op": "comp.add", "args": {"id": "film"}},
             {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "dot"}},
             {"op": "key.add", "target": "dot", "args": {"prop": "opacity", "t": "#drop+0.2", "v": 1}},
             {"op": "key.add", "target": "dot", "args": {"prop": "opacity", "t": 0.0, "v": 0}}], sam)
    keys = d.item("dot")["keys"]
    assert {k["id"]: k["t"] for k in keys} == {"dot.opacity.k_drop_p200": "#drop+0.2", "dot.opacity.k0": 0.0}
    with pytest.raises(RostrumError):
        d.apply({"op": "key.add", "target": "dot", "args": {"prop": "opacity", "t": "drop", "v": 1}}, sam)
    assert marked.moved("#drop+0.2", 0.15) == "#drop+0.35" and marked.moved("#drop+0.2", -0.2) == "#drop"
