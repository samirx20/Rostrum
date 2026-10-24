"""Painting a shared painting in place (painted.py, paint_through.py): the one mapping from a layer's px into the painting
goes there and back under every fit (with Scale, Offset, Rotation and Drift); a stroke through a layer lands where the
mapping says, on Tile carries on across the tile edge, shows in every layer using the painting, and one undo takes it
back from all of them."""
import json

import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum2d import KIND, painted

SAM = Who.person("sam")
BRUSH = {"size": 4, "color": "#ff0000", "hardness": 1.0}


@pytest.mark.parametrize("fit", ["fill", "fit", "stretch", "tile"])
def test_the_mapping_goes_there_and_back(fit):
    props = {"fillFit": fit, "fillScale": 0.7, "fillOffsetX": 13, "fillOffsetY": -9, "fillRotation": 30,
             "fillDriftX": 12, "fillDriftY": 5}
    m = painted.Mapping(props, {"w": 128, "h": 96}, (300, 380), since=1.5)
    for lx, ly in ((0, 0), (150, 190), (299, 7), (-40, 500)):
        assert m.to_layer(*m.to_painting(lx, ly)) == pytest.approx((lx, ly))
    if fit == "stretch":                          # the painting is the box: its corner pixel centres at the box's corners
        assert m.to_painting(0, 0) == pytest.approx((-0.5, -0.5)) and m.to_painting(300, 380) == pytest.approx((127.5, 95.5))


def scene() -> tuple[Document, str]:
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film"}},
             *({"op": "layer.add", "target": "film", "args": {"type": "shape", "id": i}} for i in ("c1", "c2", "c3")),
             {"op": "shape.set", "target": ["c1", "c2", "c3"], "args": {"w": 200, "h": 200}},
             {"op": "painting.add", "args": {"id": "grain", "w": 100, "h": 100, "onto": ["c1", "c2", "c3"], "fit": "tile"}}], SAM)
    return d, "grain"


def strokes(d: Document) -> list[dict]:
    return d.item("grain")["frames"][0]["paints"][0]["strokes"]


def test_a_stroke_through_a_layer_is_one_undo_step_for_every_use():
    d, pid = scene()
    before = json.dumps(d.data, sort_keys=True)
    # tile 0 is centred on the 200 px box: layer px 50..150 is the painting's 0..100; 140 -> 180 crosses its right edge
    d.apply({"op": "paint.stroke", "target": pid, "args": {**BRUSH, "points": [[140, 100], [180, 100]], "space": "layer",
                                                            "through": "c2"}}, SAM)
    got = sorted(s["points"][0][0] for s in strokes(d))
    assert got == pytest.approx([-10.5, 89.5])     # one copy carries on in the next tile, from its left edge
    for layer in ("c1", "c2", "c3"):               # every use shows the one painting
        assert d.item(layer)["fillPainting"] == pid
    d.undo(SAM)
    assert json.dumps(d.data, sort_keys=True) == before


def test_a_stroke_outside_the_painting_is_refused():
    d, pid = scene()
    d.apply({"op": "layer.fill", "target": "c2", "args": {"fit": "fit"}}, SAM)
    d.apply({"op": "shape.set", "target": "c2", "args": {"w": 400}}, SAM)        # Fit leaves bands left and right
    with pytest.raises(RostrumError, match="outside the painting"):
        d.apply({"op": "paint.stroke", "target": pid, "args": {**BRUSH, "points": [[5, 100], [20, 120]], "space": "layer",
                                                                "through": "c2"}}, SAM)
