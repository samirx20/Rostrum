"""Esc mid-drag (drag_cancel.py): the document and the history are exactly as at the press, the drag's later moves and
release do nothing, and the next drag works. Every kind of canvas drag goes through the same one place."""
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

SOURCE = '''
comp("c", name="Scene", width=1920, height=1080, fps=30, duration=4)
for i in range(3):
    shape(f"tile{i}", w=100, h=100, x=400 + 150 * i, y=300, rotation=20 * i)
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


def _drags(b):
    """(name, begin, a few moves) for each canvas drag of one layer."""
    return [
        ("move", b.beginMove, lambda: [b.moveBy(30 * f, 10 * f) for f in (1, 2, 3)]),
        ("copy", b.beginCopyMove, lambda: [b.moveBy(30 * f, 0) for f in (1, 2)]),
        ("resize", lambda: b.beginResize(1, 1), lambda: [b.resizeBy(20 * f, 15 * f, False, False) for f in (1, 2)]),
        ("rotate", b.beginRotate, lambda: [b.rotateTo(600 + f, 200 + 40 * f, False) for f in (0, 1, 2)]),
    ]


@pytest.mark.parametrize("which", ["move", "copy", "resize", "rotate"])
def test_esc_puts_one_layer_back(b, which):
    from screen2d import drag_cancel
    b.select("tile1")
    before, n = b.doc.data, len(b.doc.history.changes)
    name, begin, moves = next(d for d in _drags(b) if d[0] == which)
    assert begin()
    moves()
    assert drag_cancel.cancel(b) is True
    assert b.doc.data == before and len(b.doc.history.changes) == n
    moves()                                                     # the pointer still moves, then lets go: nothing
    b.endDrag()
    assert b.doc.data == before and len(b.doc.history.changes) == n
    assert begin()                                              # and the next drag is one undo step as ever
    moves()
    b.endDrag()
    assert len(b.doc.history.changes) == n + 1


def test_esc_puts_many_layers_back(b):
    from screen2d import drag_cancel
    b.selectMany(["tile0", "tile1", "tile2"])
    before, n = b.doc.data, len(b.doc.history.changes)
    assert b.beginMove()
    for dx in (10, 25, 40):
        b.moveBy(dx, 5)
    assert drag_cancel.cancel(b)
    b.endDrag()
    assert b.doc.data == before and len(b.doc.history.changes) == n


def test_esc_with_no_drag_does_its_other_jobs(b):
    from screen2d import drag_cancel
    assert drag_cancel.cancel(b) is False and not drag_cancel.drag_open(b)
