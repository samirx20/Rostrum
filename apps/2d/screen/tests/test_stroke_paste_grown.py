"""Strokes moved past their drawing's edge grow it; the picked strokes' outline, Copy and Paste then follow the drawing's
new place (a stale place stretched them: a paste landed about a quarter off). stroke_select.py `_place_again`."""
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")


def _centre(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def test_paste_after_a_move_that_grew_the_drawing_lands_beside_the_strokes(tmp_path):
    from PySide6.QtTest import QTest
    from rostrum_gui.app import qt_app
    from screen2d.files2d import blank
    from screen2d.session import Session
    from screen2d.steps import do_step
    from screen2d.stroke_clip import PASTE_STEP
    app = qt_app()
    session = Session((1646, 900), None)
    session.files.put(blank(tmp_path))
    QTest.qWait(800)
    b, win = session.bridge, session.win
    try:
        for s in ("tool draw", "draw 1500 500 1600 520 1700 540", "lasso 1450,450 1750,450 1750,600 1450,600",
                  "strokesmove -700 -300"):
            do_step(b, win, s)
            QTest.qWait(300)
        sel = b.strokeSelect
        d = sel._target()
        assert d.get("w", 0) > 512, "the move should have grown the drawing"
        moved = _centre(sel._comp[sel._ids[0]])
        sel.copy()
        assert sel.paste()
        QTest.qWait(300)
        sel._seen_on(sel._target())                      # where the strokes truly are now
        true = sorted(_centre(sel._to_comp(s["points"])) for s in sel._strokes(sel._target()))
        assert true[0] == pytest.approx(moved, abs=1)
        assert true[1] == pytest.approx((moved[0] + PASTE_STEP, moved[1] + PASTE_STEP), abs=1)
    finally:
        app.processEvents()
        session.close()
