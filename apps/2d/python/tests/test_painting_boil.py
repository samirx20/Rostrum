"""A painting that boils (frame.add on a painting, design 2d-painted-fill § 3.8): each layer using it runs its drawings
from its own start, round and round, and a frame tool painting in place finds where that layer next shows a drawing.
Silent if broken: every use would show drawing 1 for ever, or the playhead would jump to the wrong moment."""
from rostrum_core import Document, Who

from rostrum2d import KIND, painted_fill

SAM = Who.person("sam")


def test_a_painting_boils_on_each_use_from_its_own_start():
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film"}},
             *({"op": "layer.add", "target": "film", "args": {"type": "shape", "id": i}} for i in ("a", "b")),
             {"op": "shape.set", "target": ["b"], "args": {"start": 1.0}},
             {"op": "painting.add", "args": {"id": "rain", "w": 64, "h": 64, "onto": ["a", "b"], "fit": "tile"}},
             {"op": "frame.add", "target": ["rain"], "args": {"at": 2}},
             {"op": "frame.add", "target": ["rain"], "args": {"at": 4}}], SAM)
    rain = d.item("rain")
    assert rain["eachFrame"] and [f["at"] for f in rain["frames"]] == [0, 2, 4]
    fps, first = d.item("film")["fps"], rain["frames"][0]
    b = d.item("b")
    start = round(fps)                                    # b starts at 1 s: drawing 1 there, not where a is
    assert painted_fill.shown(b, rain, start, fps) is first
    assert painted_fill.shown(b, rain, start + 2, fps) is rain["frames"][1]
    later = painted_fill.when_shown(b, rain, 4, start + 3, fps)
    assert later >= start + 3 and painted_fill.shown(b, rain, later, fps) is rain["frames"][2]
