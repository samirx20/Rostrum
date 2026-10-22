"""The kit's drag and snap rules (INTERACTION.md 1.10-1.12) that every app's drags rely on: the strongest target within
6 screen px wins and nothing farther is caught; a marker drop ties; Esc leaves the document as it was with no undo
step; zooming at the pointer keeps the canvas point under it."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from rostrum_core import Who, toy

from rostrum_gui.canvasview import CanvasView
from rostrum_gui.drag import PointerDrag
from rostrum_gui.edits import Scrub
from rostrum_gui.snap import Target, label, snap, tie


def test_snap_picks_the_strongest_target_within_6_px_and_nothing_beyond():
    found = [Target("beat", "beat 3", 1.02), Target("playhead", "playhead", 0.97), Target("marker", "drop", 1.05)]
    c = snap(1.0, found, scale=100)                              # 100 px per second: 6 px = 0.06 s
    assert (c.value, c.name) == (1.05, "drop")                   # a marker beats a nearer playhead and beat
    assert label("+6 f", c) == "+6 f · drop" and tie(c.value, c) == "#drop"
    c = snap(1.0, found[:2], scale=100)
    assert c.name == "playhead"
    far = snap(2.0, found, scale=100, step=0.5)                  # nothing within 6 px: the whole step
    assert far.target is None and far.value == 2.0
    assert snap(1.0, found, scale=100, free=True).target is None  # Ctrl: free
    with pytest.raises(ValueError):
        snap(1.0, found, scale=0)
    with pytest.raises(ValueError):
        Target("wobble", "x", 1.0)


def test_esc_during_a_drag_leaves_the_document_unchanged():
    doc = toy.sample()
    before, steps = doc.item("cam_1")["focal"], len(doc.history.changes)
    d = PointerDrag(0, 0, lambda: Scrub(doc, Who.person("sam"), "cam_1", "focal"))
    assert not d.move(3, 0)                                      # under 4 px: still a click
    assert d.move(10, 0)
    d.preview(before + 10)
    assert doc.item("cam_1")["focal"] == before + 10
    d.cancel()
    assert d.release() is None
    assert doc.item("cam_1")["focal"] == before and len(doc.history.changes) == steps


def test_zoom_at_the_pointer_keeps_the_canvas_point_under_it():
    v = CanvasView()
    v.setViewSize(800, 600)
    v.panBy(37, -12)
    under = v.to_canvas(250, 410)
    v.zoomAt(3.7, 250, 410)
    assert v.to_canvas(250, 410) == pytest.approx(under)
    v.wheel(0, 240, 250, 410, 0x04000000)                        # Ctrl+wheel, two notches
    assert v.to_canvas(250, 410) == pytest.approx(under)
