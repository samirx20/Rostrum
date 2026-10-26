"""A canvas drag of several picked layers (ghost_move.py): the moves only tell the engine where the layers are, the
document changes once, at the drop, as one undo step; a locked layer among them still refuses the move."""
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

SOURCE = '''
comp("c", name="Scene", width=1920, height=1080, fps=30, duration=4)
for i in range(3):
    shape(f"tile{i}", w=100, h=100, x=400 + 150 * i, y=300)
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


def xs(b):
    return [b.doc.item(f"tile{i}")["x"] for i in range(3)]


def test_many_layers_move_at_the_drop_as_one_step(b):
    b.selectMany(["tile0", "tile1", "tile2"])
    n = len(b.doc.history.changes)
    assert b.beginMove()
    b.snap.keys(True, False)                                   # Ctrl held: no snapping
    assert b._ghost is not None
    for dx in (10, 25, 40):
        b.moveBy(dx, 5)
    assert xs(b) == [400, 550, 700] and len(b.doc.history.changes) == n     # nothing changed mid-drag
    b.endDrag()
    assert xs(b) == [440, 590, 740] and [b.doc.item(f"tile{i}")["y"] for i in range(3)] == [305] * 3
    assert len(b.doc.history.changes) == n + 1
    b.undo()
    assert xs(b) == [400, 550, 700]


def test_a_locked_layer_among_them_still_refuses(b):
    b.select("tile1")
    b.toggleSwitch("tile1", "locked")
    b.selectMany(["tile0", "tile1", "tile2"])
    if b.beginMove():
        assert b._ghost is None                                # checked at the press: the per-move way says why
        b.moveBy(30, 0)
        b.endDrag()
    assert b.doc.item("tile1")["x"] == 550
