"""paint.fill (ops_fill.py): a click inside a closed line drawing fills it as one sharp fill item, in one undo step;
a click that has nothing closed to fill is refused loudly and changes nothing."""
import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum2d import KIND

SAM = Who.person("sam")
# A square of lines on a 200 × 200 drawing, with an 8 px gap in its right side (closed by Close gaps: medium).
SQUARE = [[[40, 40], [160, 40]], [[160, 40], [160, 95]], [[160, 107], [160, 160]], [[160, 160], [40, 160]],
          [[40, 160], [40, 40]]]


def drawn() -> Document:
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film", "width": 200, "height": 200, "duration": 1}},   # made at its size: its frame at home
             {"op": "layer.add", "target": "film", "args": {"type": "drawing", "id": "ink"}},
             {"op": "drawing.set", "target": "ink", "args": {"w": 200, "h": 200, "x": 100, "y": 100}}], SAM)
    d.apply([{"op": "paint.stroke", "target": "ink", "args": {"points": pts, "space": "canvas", "size": 4, "hardness": 1}}
             for pts in SQUARE], SAM)
    return d


def fills(d):
    return [s for s in d.item("ink")["frames"][0]["paints"][0]["strokes"] if s["type"] == "fill"]


def test_fill_is_one_step_and_refuses_an_open_area():
    d = drawn()
    with pytest.raises(RostrumError, match="not closed"):            # the gap leaks with Close gaps: small
        d.apply({"op": "paint.fill", "target": "ink", "args": {"at": [[100, 100]], "space": "canvas"}}, SAM)
    with pytest.raises(RostrumError, match="on a line"):
        d.apply({"op": "paint.fill", "target": "ink", "args": {"at": [[40, 100]], "space": "canvas"}}, SAM)
    assert fills(d) == []
    d.apply({"op": "paint.fill", "target": "ink",
             "args": {"at": [[100, 100]], "space": "canvas", "gap": "medium", "color": "#ff0000"}}, SAM)
    (f,) = fills(d)
    xs = [p[0] for p in f["points"]]
    assert f["color"] == "#ff0000" and 36 <= min(xs) <= 44 and 156 <= max(xs) <= 164   # up to (under) the lines
    d.undo(SAM)
    assert fills(d) == []
