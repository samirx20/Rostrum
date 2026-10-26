"""A number typed in the settings panel (the critic's round 10): with several layers picked, X moves them together and
keeps their spacing (it never stacks them all on one X), as one undo step; a typed half of Tilt keeps no keys on the
other half that only hold one value (no dead Tilt X diamonds after a Tilt Y flip)."""
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

SOURCE = '''
comp("c", name="Scene", width=1920, height=1080, fps=30, duration=4)
for i in range(3):
    shape(f"tile{i}", w=100, h=100, x=400 + 150 * i, y=300 + 20 * i)
shape("card", w=300, h=200, x=960, y=700)
'''


@pytest.fixture
def b(tmp_path):
    from rostrum_core import Document
    from rostrum2d import KIND, run_source
    from rostrum_gui.app import qt_app
    from screen2d.session import Session
    app = qt_app()
    session = Session((1646, 900), None)
    doc = Document.new(KIND, folder=str(tmp_path), item="proj")
    doc.run_script("a.py", run_source(SOURCE, "a.py"))
    session.files.put(doc)
    yield session.bridge
    app.processEvents()
    session.close()


def test_a_typed_x_moves_several_together_as_one_step(b):
    xs = lambda: [b.doc.item(f"tile{i}")["x"] for i in range(3)]  # noqa: E731
    b.selectMany(["tile0", "tile1", "tile2"])
    assert b.setValue("x", 1300)
    assert xs() == [1300, 1450, 1600]
    assert b.setValue("y", 100)
    assert [b.doc.item(f"tile{i}")["y"] for i in range(3)] == [100, 120, 140]
    b.undo()
    b.undo()
    assert xs() == [400, 550, 700]
    assert b.setValue("rotation", 30)                          # any other field: the typed value on each
    assert [b.doc.item(f"tile{i}")["rotation"] for i in range(3)] == [30, 30, 30]


def test_a_tilt_y_flip_leaves_no_tilt_x_keys(b):
    from rostrum_core.keys import keys_of
    b.select("card")
    b.setTime(1.0)
    b.toggleAnimate("tiltX")                                   # the pair's diamond: both halves keyed at 0
    b.setTime(0.4)
    assert b.setValue("tiltY", -90)                            # Y now flips: X only held 0
    card = b.doc.item("card")
    assert keys_of(card, "tiltX") == [] and [k["t"] for k in keys_of(card, "tiltY")] == [0.4, 1.0]
    b.setTime(2.0)
    b.toggleAnimate("tiltX")                                   # the diamond again: only the half that moves
    card = b.doc.item("card")
    assert keys_of(card, "tiltX") == [] and len(keys_of(card, "tiltY")) == 3
    b.setTime(3.0)
    assert b.setValue("tiltX", 20)                             # the still half typed: keyed from here, 0 before
    assert [(k["t"], k["v"]) for k in keys_of(b.doc.item("card"), "tiltX")] == [(0.4, 0), (1.0, 0), (2.0, 0), (3.0, 20)]
