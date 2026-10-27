"""Keys typed while a click missed a box never act on the whole scene (hand maker row 5: Ctrl+A then a capital A wrapped
all 20 layers into an auto layout): Ctrl+A picks layers only from the canvas or the timeline, and Auto layout's one key
never acts on a Ctrl+A pick."""
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

SRC = 'comp("c", width=1920, height=1080, fps=25, duration=2)\n' + "".join(
    f'shape("s{i}", x={200 + 100 * i}, y=300, w=60, h=60)\n' for i in range(6))


def test_ctrl_a_from_the_settings_and_shift_a_after_ctrl_a_leave_the_scene_alone(tmp_path):
    from PySide6.QtTest import QTest
    from rostrum_core import Document
    from rostrum2d import KIND, run_source
    from rostrum_gui.app import qt_app
    from screen2d.session import Session
    app = qt_app()
    session = Session((1646, 900), None)
    doc = Document.new(KIND, folder=str(tmp_path), item="proj")
    doc.run_script("a.py", run_source(SRC, "a.py"))
    session.files.put(doc)
    QTest.qWait(600)
    b = session.bridge
    try:
        b.select("s0")
        b.setFocusArea("settings")
        b._hub.key("select_all")
        assert b.selected_layers() == ["s0"]                     # a missed box: the pick stays
        b.setFocusArea("canvas")
        b._hub.key("select_all")
        assert len(b.selected_layers()) == 6
        b._hub.key("auto_layout")
        assert {l["id"] for l in b.comp()["layers"]} >= {f"s{i}" for i in range(6)}     # nothing wrapped
        b._select(["s0", "s1"])                                  # picked by hand: it runs
        b._hub.key("auto_layout")
        assert not {"s0", "s1"} & {l["id"] for l in b.comp()["layers"]}
    finally:
        app.processEvents()
        session.close()
