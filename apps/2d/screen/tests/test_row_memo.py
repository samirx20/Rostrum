"""The settings panel's kept rows (rostrum_gui/row_memo.py) never show stale settings: after each kind of change (a
value, a key, a value that opens a folded group, a time, an undo), the panel of one layer and of several equals the
panel worked out from nothing. A wrong patch would show an old value or a missing row with no error anywhere."""
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

SRC = '''
comp("c", width=1920, height=1080, fps=25, duration=4)
for i in range(6):
    d = shape(f"d{i}", shape="ellipse", w=60, h=60, fill="#ff7a59", x=200 + i * 100, y=300)
    d.key("scale", {0.0: 0.0, 1.0: 1.0})
text("t", text="Hi", x=500, y=700)
'''


@pytest.fixture
def b(tmp_path):
    from rostrum_core import Document
    from rostrum2d import KIND, run_source
    from rostrum_gui.app import qt_app
    from screen2d.session import Session
    from PySide6.QtTest import QTest
    app = qt_app()
    session = Session((1646, 900), None)
    doc = Document.new(KIND, folder=str(tmp_path), item="proj")
    doc.run_script("a.py", run_source(SRC, "a.py"))
    session.files.put(doc)
    QTest.qWait(500)
    yield session.bridge
    app.processEvents()
    session.close()


def _same_as_fresh(b, ids):
    b.selectMany(ids)
    kept = b._rows()
    b._kit.memo.clear()
    assert kept == b._rows()


def test_kept_rows_equal_fresh_rows_after_each_change(b):
    dots = [f"d{i}" for i in range(6)]
    for sel in (dots, ["d0"], dots + ["t"]):
        _same_as_fresh(b, sel)                       # (fills the memo)
    steps = [lambda: b.setValue("x", 333), lambda: b.setValue("opacity", 0.5), lambda: b.setValue("rotation", 30),
             lambda: b.toggleAnimate("rotation"), lambda: b.setTime(0.5), lambda: b.undo(), lambda: b.undo(),
             lambda: b.setValue("blend", "multiply")]
    for n, step in enumerate(steps):
        b.selectMany(dots[:3] if n % 2 else dots)
        b._rows()                                    # kept as they are now
        step()
        for sel in (dots, dots[:3], ["d1"], dots + ["t"]):
            _same_as_fresh(b, sel)
