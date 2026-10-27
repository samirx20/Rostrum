"""A layer row pulled to a new place in the list is one undo step (row_drag.py: the gesture from pull to drop), Esc while
it is held puts everything back with no step (drag_cancel.py finds it), and Ctrl+A says how many layers it picked."""
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


def order(b):
    return [lay["id"] for lay in b.comp()["layers"] if lay["id"].startswith("tile")]


def test_a_row_drag_is_one_undo_step(b):
    n, was = len(b.doc.history.changes), order(b)
    assert b.rowDrag.begin("tile0")
    assert b.rowDrag.drop("tile2", "above")                # the top of the stack is listed first: tile0 goes over tile2
    assert order(b) != was and len(b.doc.history.changes) == n + 1
    b.undo()
    assert order(b) == was


def test_esc_mid_row_drag_puts_it_back(b):
    from screen2d import drag_cancel
    n, was = len(b.doc.history.changes), order(b)
    assert b.rowDrag.begin("tile0")
    gone = []
    b.rowDrag.cancelled.connect(lambda: gone.append(True))
    assert drag_cancel.cancel(b)                           # what Esc does while the button is held
    assert gone and not b.rowDrag.drop("tile2", "above")   # the release after Esc changes nothing
    assert order(b) == was and len(b.doc.history.changes) == n


def test_ctrl_a_says_how_many(b):
    b.selectAllKey()
    assert len(b.selected_layers()) >= 3 and b.status.startswith("Picked ")
