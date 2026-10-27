"""layer.anchor moves the anchor point in one step: with keep_place the layer's corners stay exactly where they were
(turned, scaled and mirrored layers too), without it the layer moves so the new anchor sits where the old one was; an
animated Position gets keys at `at`. (The canvas's anchor ring makes the same call: screen/tests/test_anchor_drag.py.)"""
from rostrum_core import Document, Who
from rostrum_core.keys import keys_of

from rostrum2d import KIND, boxes, run_source

SRC = '''
comp("c", width=640, height=360, duration=2)
shape("a", w=80, h=40, x=200, y=100, rotation=35, scale=1.5, scaleX=-1)
s = shape("b", w=60, h=60, x=300, y=200)
s.key("x", {0.0: 300, 1.0: 400})
'''


def _doc():
    d = Document.new(KIND)
    d.run_script("t.py", run_source(SRC, "t.py"))
    return d


def _anchor(d, target, **args):
    return d.apply([{"op": "layer.anchor", "target": [target], "args": args}], Who.person("sam"))


def _same(p, q):
    return all(abs(a - b) < 0.01 for c, e in zip(p, q) for a, b in zip(c, e))


def test_keep_place_leaves_a_turned_mirrored_layer_where_it_shows_in_one_step():
    d = _doc()
    before, n = boxes.corners(d.item("a")), len(d.history.changes)
    _anchor(d, "a", x=0.0, y=1.0)
    a = d.item("a")
    assert (a["anchorX"], a["anchorY"]) == (0.0, 1.0)
    assert _same(boxes.corners(a), before) and len(d.history.changes) == n + 1


def test_without_keep_place_the_new_anchor_lands_on_the_old_place():
    d = _doc()
    _anchor(d, "a", x=1.0, keep_place=False)
    a = d.item("a")
    assert (a["x"], a["y"], a["anchorX"], a["anchorY"]) == (200, 100, 1.0, 0.5)


def test_an_animated_position_gets_keys_and_still_shows_in_place():
    d = _doc()
    before = boxes.corners(d.item("b"), 0.5)
    _anchor(d, "b", x=0.0, y=0.0, at=0.5)
    b = d.item("b")
    assert 0.5 in [k["t"] for k in keys_of(b, "x")]
    assert _same(boxes.corners(b, 0.5), before)


def test_a_pivot_in_comp_px_keeps_a_grown_drawing_still():
    """FRICTION A2-3: pivot(x, y) puts the anchor on a comp point with no box maths; the picture does not move, and the
    canvas growing round strokes painted past its left edge (after or before the call) keeps it on that spot."""
    import math
    import pytest
    from rostrum2d.evaluate import resolve

    def where(src):                                     # the comp px of the stroke's first point at 0 s
        d = Document.new(KIND)
        d.run_script("s.py", run_source('comp("c")\nb = drawing("beam", x=900, y=500, w=400, h=300, rotation=20, scale=1.5)\n'
                                        'ink = b.frame(0).paint()\n' + src, "s.py"))
        item = d.item("beam")
        p = resolve(item, 0)
        sx, sy = p["scale"] * p["scaleX"], p["scale"] * p["scaleY"]
        u = item["frames"][0]["paints"][0]["strokes"][0]["points"][0]
        vx, vy = (u[0] - p["anchorX"] * p["w"]) * sx, (u[1] - p["anchorY"] * p["h"]) * sy
        c, s = math.cos(math.radians(p["rotation"])), math.sin(math.radians(p["rotation"]))
        return (p["x"] + c * vx - s * vy, p["y"] + s * vx + c * vy), p
    stroke = 'ink.stroke([(-900, 100), (300, 150)], size=20)\n'
    plain, _ = where(stroke)
    for src in (stroke + 'b.pivot(1000, 520)\n', 'b.pivot(1000, 520)\n' + stroke):
        moved, p = where(src)
        assert moved == pytest.approx(plain, abs=0.05)                       # nothing moved (values kept to 4 places)
        assert (p["x"], p["y"]) == pytest.approx((1000, 520), abs=0.05)      # the anchor is on the point
