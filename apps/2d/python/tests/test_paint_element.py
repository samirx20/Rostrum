"""Paint on an element (ops_paint.py, engine stage_paint.rs): with Keep inside the outline on, paint never shows outside
the element's own pixels; off, it covers the box. One paint.stroke (frame, paint layer and paint size made on the way)
is one undo step."""
import pytest
from PIL import Image
from rostrum_core import Document, Who

from rostrum2d import KIND, settings
from rostrum2d.scene import describe

SAM = Who.person("sam")
# An ellipse 200 × 100 centred in a 400 × 300 black frame: its box is x 100..300, y 100..200.
# The stroke runs along the box's top edge, past both sides: there the box's corners are outside the ellipse.
STROKE = {"points": [[90, 108], [310, 108]], "size": 16, "color": "#ff0000", "hardness": 1.0}


def painted_ellipse(inside: bool) -> Document:
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film"}},
             {"op": "comp.set", "target": "film", "args": {"width": 400, "height": 300, "duration": 1}},
             {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "egg"}},
             {"op": "shape.set", "target": "egg", "args": {"shape": "ellipse", "x": 200, "y": 150, "w": 200, "h": 100,
                                                            "fill": "#0000ff"}}], SAM)
    d.apply({"op": "paint.stroke", "target": "egg", "args": STROKE}, SAM)
    if not inside:
        d.apply({"op": "shape.set", "target": "egg", "args": {"paintInside": False}}, SAM)
    return d


def test_one_paint_stroke_is_one_undo_step():
    d = painted_ellipse(True)
    egg = d.item("egg")
    assert (egg["paintW"], egg["paintH"]) == (200, 100)                 # the paint size comes from the box
    assert egg["frames"][0]["paints"][0]["strokes"][0]["points"][0][:2] == [-10.5, 7.5]    # composition px -> canvas px (pixel centres)
    d.undo(SAM)
    egg = d.item("egg")
    assert not egg.get("frames") and not egg.get("paintW")


@pytest.mark.skipif(settings.engine_exe() is None, reason="needs a built engine")
def test_paint_stays_inside_the_outline(tmp_path):
    from rostrum2d.engine import Engine
    seen = {}
    with Engine() as eng:
        for inside in (True, False):
            eng.load(describe(painted_ellipse(inside).data))
            png = tmp_path / f"inside_{inside}.png"
            eng.still(0.0, png)
            seen[inside] = Image.open(png).convert("RGB")
    corner, middle = (110, 108), (200, 108)                  # in the box but outside the ellipse; inside both
    assert seen[True].getpixel(corner) == (0, 0, 0)          # kept inside: nothing outside the ellipse
    assert seen[True].getpixel(middle)[0] > 200 and seen[True].getpixel(middle)[2] < 60
    assert seen[False].getpixel(corner)[0] > 200             # not kept inside: the whole box takes paint
    assert seen[True].getpixel((60, 108)) == seen[False].getpixel((60, 108)) == (0, 0, 0)    # never outside the box
