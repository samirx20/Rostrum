"""A drawing grows with its strokes (paint_grow.py, paint_overflow.py): growing left and up keeps every stroke where it
shows (the engine's own placement, turned, scaled and with a keyed anchor), and past 8192 px a side the stroke starts
a new drawing beside it, in one undo step. Silent breakage here moves a person's painting or loses a stroke."""
import pytest
from rostrum_core import Document, Who

from rostrum2d import KIND, settings
from rostrum2d.paint_overflow import note

SAM = Who.person("sam")
INK = {"size": 10, "color": "#ff0000", "hardness": 1.0, "space": "canvas"}


def drawing_doc(w=200, h=100) -> Document:
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film", "width": 400, "height": 300, "duration": 1}},
             {"op": "layer.add", "target": "film", "args": {"type": "drawing", "id": "sky", "name": "sky"}},
             {"op": "drawing.set", "target": "sky", "args": {"w": w, "h": h, "x": 200, "y": 150, "rotation": 30, "scale": 1.5}},
             {"op": "key.add", "target": "sky", "args": {"prop": "anchorX", "t": 0.0, "v": 0.5}},
             {"op": "key.add", "target": "sky", "args": {"prop": "anchorX", "t": 1.0, "v": 0.2}}], SAM)
    d.apply({"op": "paint.stroke", "target": "sky", "args": {**INK, "points": [[50, 40], [150, 60]]}}, SAM)
    return d


def _seen(d: Document, t: float) -> list:
    """The first stroke's points in composition px at `t`, through the engine's own placement of the layer."""
    from rostrum2d import placement
    from rostrum2d.evaluate import resolve
    item = d.item("sky")
    pts = item["frames"][0]["paints"][0]["strokes"][0]["points"]
    return placement.comp_points(item, resolve(item, t), placement.place_at(d.data, "sky", t), pts)


@pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")
def test_growing_left_and_up_keeps_every_stroke_where_it_shows():
    d = drawing_doc()
    before = {t: _seen(d, t) for t in (0.0, 0.5)}
    d.apply({"op": "paint.stroke", "target": "sky", "args": {**INK, "points": [[-40, -30], [20, 20]]}}, SAM)
    sky = d.item("sky")
    assert (sky["w"], sky["h"]) == (200 + 256, 100 + 256)              # grown left and up, one chunk each
    strokes = sky["frames"][0]["paints"][0]["strokes"]
    assert strokes[0]["points"][0][:2] == [306, 296]                    # the old stroke moved with the canvas
    assert strokes[1]["points"][0][:2] == [216, 226]                    # the new one where it was asked for
    assert sky["frames"][0]["paperX"] == 256 and sky["frames"][0]["paperY"] == 256   # the grain moved with them
    for t, pts in before.items():
        for a, b in zip(pts, _seen(d, t)):
            assert a[0] == pytest.approx(b[0], abs=0.02) and a[1] == pytest.approx(b[1], abs=0.02)


def test_past_8192_a_stroke_starts_a_new_drawing_in_one_undo_step():
    d = drawing_doc(8000, 100)
    change = d.apply({"op": "paint.stroke", "target": "sky", "args": {**INK, "points": [[7900, 50], [8300, 60]]}}, SAM)
    sky = d.item("sky")
    assert sky["w"] == 8000 and len(sky["frames"][0]["paints"][0]["strokes"]) == 1      # never a silent crop
    new = d.item(next(lay["id"] for lay in d.item("film")["layers"] if lay.get("name") == "sky 2"))
    stroke = new["frames"][0]["paints"][0]["strokes"][0]
    assert 0 <= stroke["points"][0][0] < new["w"] and stroke["points"][1][0] < new["w"]
    assert (new["rotation"], new["scale"], len(new["keys"])) == (30, 1.5, 2)              # it sits where the old one does
    ox = 7900 - stroke["points"][0][0]                                                    # its canvas (0, 0) in the old's px
    assert new["anchorX"] * new["w"] == pytest.approx(sky["anchorX"] * sky["w"] - ox)
    assert note(change, d) == "'sky' is at its largest; this stroke started 'sky 2'"
    d.undo(SAM)
    assert not any(lay.get("name") == "sky 2" for lay in d.item("film")["layers"])
    assert len(d.item("sky")["frames"][0]["paints"][0]["strokes"]) == 1
