"""Fill the frame must really cover the frame for a turned, stretched, off-centre layer (silent breakage otherwise)."""
import math

from rostrum_core import Document, Who

from rostrum2d import KIND, boxes

SAM = Who.person("sam")


def _inside(pt, corners):
    """Is pt inside the (convex) quad, corners in order?"""
    sides = [(b[0] - a[0]) * (pt[1] - a[1]) - (b[1] - a[1]) * (pt[0] - a[0]) for a, b in zip(corners, corners[1:] + corners[:1])]
    return all(s >= -1e-3 for s in sides) or all(s <= 1e-3 for s in sides)


def test_cover_a_turned_stretched_layer_leaves_no_edge_and_inside_fits():
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film"}}, {"op": "comp.size", "target": "film", "args": {"size": "vertical"}},
             {"op": "layer.add", "target": "film", "args": {"type": "shape", "id": "p"}},
             {"op": "shape.set", "target": "p", "args": {"x": 100, "y": 1500, "w": 400, "h": 300, "rotation": 17, "scaleX": 1.5, "anchorX": 0.2}}], SAM)
    assert (d.item("film")["width"], d.item("film")["height"]) == (1080, 1920)
    d.apply({"op": "layer.fill_frame", "target": "p", "args": {}}, SAM)
    quad = boxes.corners(d.item("p"))
    # the frame took the new size about its centre (960, 540): it sees x 420..1500, y -420..1500
    assert all(_inside(c, quad) for c in ((420, -420), (1500, -420), (1500, 1500), (420, 1500)))
    d.apply({"op": "layer.fill_frame", "target": "p", "args": {"mode": "inside"}}, SAM)
    x0, y0, x1, y1 = boxes.box(d.item("p"))
    assert x0 >= 419.9 and y0 >= -420.1 and x1 <= 1500.1 and y1 <= 1500.1 and (abs(x1 - 1500) < 0.1 or abs(y1 - 1500) < 0.1)
    assert math.isclose((x0 + x1) / 2, 960, abs_tol=0.1)
