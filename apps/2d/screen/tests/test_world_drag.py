"""Spec test 3, through the screen's own code (bounds.boxes + the drag's parent_delta, as drags.py and handle_slots.py
use them): the canvas shows the world, a layer is boxed where the world view draws it, and a pointer move of (dx, dy)
becomes the layer's own x / y change that moves it by exactly (dx, dy) there, at depth 0, 3 and -0.5 and pinned, with
the frame zoomed 2x and (for the pinned one) turned 30 degrees. Points hand-computed from FRAME.md's world maths."""
import sys
from pathlib import Path

import pytest
from rostrum_core import Document

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum2d import KIND, run_source  # noqa: E402
from screen2d import bounds, snap as S  # noqa: E402
from rostrum2d.frame import view  # noqa: E402

SRC = '''
comp("c", width=1920, height=1080, fps=10, duration=2)
frame(x=1160, y=640, zoom=2, rotation=30)
shape("d0", w=40, h=40, x=500, y=300, depth=0, anchorX=0, anchorY=0)
shape("d3", w=40, h=40, x=500, y=300, depth=3, anchorX=0, anchorY=0)
shape("dn", w=40, h=40, x=500, y=300, depth=-0.5, anchorX=0, anchorY=0)
shape("pin", w=40, h=40, x=1000, y=600, screenLock=True, anchorX=0, anchorY=0)
'''
# The frame turned 30 degrees only matters to a pinned layer in the world view (a depth layer is carried back through
# the plain frame, spec 8.3), so the depth layers' points are the zoom-only ones: world = F + k (p - P), k = 2^(s-1) / ... = z^s / z.
K3, K_N = 2 ** 0.25 / 2, 2.0               # depth 3: s = 1/4;  depth -0.5: s = 2 (z^2 / z = 2)
WHERE = {"d0": (500, 300), "d3": (1160 - 510 * K3, 640 - 265 * K3), "dn": (1160 + K_N * (500 - 1360), 640 + K_N * (300 - 740)),
         "pin": (1160 + (40 * 0.866025 - 60 * 0.5) / 2, 640 + (40 * 0.5 + 60 * 0.866025) / 2)}
PER_PX = {"d0": 1.0, "d3": 1 / K3, "dn": 1 / K_N}      # own px moved per world px of pointer (x only at 0 turn)


@pytest.fixture(scope="module")
def comp():
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SRC, "s.py"))
    return doc.item("c")


def box(comp, layer):
    return next(b for b in bounds.boxes(comp, 0) if b["id"] == layer)


@pytest.mark.parametrize("layer", ["d0", "d3", "dn", "pin"])
def test_boxed_where_drawn_and_a_drag_lands_under_the_pointer(comp, layer):
    b = box(comp, layer)
    assert (b["x"], b["y"]) == pytest.approx(WHERE[layer], abs=0.01)         # the box's top-left (anchor 0, 0) in world px
    dx, dy = bounds.parent_delta(b, 100, 0)                                  # the pointer moves 100 world px right
    if layer in PER_PX:
        assert (dx, dy) == pytest.approx((100 * PER_PX[layer], 0), abs=0.01)
    else:                                                                    # pinned: its px turn and shrink with the frame
        assert (dx, dy) == pytest.approx((2 * 100 * 0.866025, -2 * 100 * 0.5), abs=0.01)
    moved = {**comp, "layers": [{**lay, "x": lay["x"] + dx, "y": lay["y"] + dy} if lay["id"] == layer else lay for lay in comp["layers"]]}
    after = box(moved, layer)
    assert (after["x"] - b["x"], after["y"] - b["y"]) == pytest.approx((100, 0), abs=0.01)
    assert bounds.pick(comp, 0, b["x"] + b["w"] / 2 + 0.01, b["y"] + b["h"] / 2) == layer     # a click where it is drawn picks it


def test_items_snap_to_the_frame_where_it_is():
    from rostrum2d.frame.view import Shot
    straight = S.frame_target(1920, 1080, Shot(1160, 640, 2, 0, 960, 540))
    assert straight == (0, (680, 370, 1640, 910))                           # 1920 / 2 x 1080 / 2 about (1160, 640)
    sideways = S.frame_target(1920, 1080, Shot(1160, 640, 2, 90, 960, 540))
    assert sideways == (0, (890, 160, 1430, 1120))                         # swapped at 90 degrees
    assert S.frame_target(1920, 1080, Shot(1160, 640, 2, 30, 960, 540)) == (0, (1160, 640, 1160, 640))   # turned: its centre only
    assert S.frame_target(1920, 1080) == (0, (0.0, 0.0, 1920.0, 1080.0))
