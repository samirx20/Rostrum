"""Keys typed into a text box stay in it (critic 2d-final row 1: typed names became shortcuts, M made markers, Shift+H
mirrored a group, Space played, Backspace deleted the layer, Ctrl+A picked every layer). Real key presses and clicks into
the real window: every editable box of a text layer's settings (a click on its padding, not its words), the time box, a
rename right after Ctrl+G and right after drawing. Only that box's own value may change; layers, markers, playhead,
pick, flips and playback stay as they were. Needs the built engine like any scripted run."""
import json
import sys
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

KEYS = "Mh m.5 "        # letters that are shortcuts (M marker, H, Space play), a dot (next key), a digit


@pytest.fixture
def screen(tmp_path):
    from rostrum_core import Document
    from rostrum2d import KIND, run_source
    from rostrum_gui.app import qt_app
    from screen2d.sample import SOURCE
    from screen2d.session import Session
    app = qt_app()
    session = Session((1646, 900), None)
    doc = Document.new(KIND, folder=str(tmp_path), item="proj")
    doc.run_script("a.py", run_source(SOURCE, "a.py"))
    session.files.put(doc)
    from PySide6.QtTest import QTest
    QTest.qWait(800)
    yield session.bridge, session.win
    app.processEvents()
    session.close()


def _state(b):
    return {"doc": json.dumps(b.doc.data, sort_keys=True, default=str), "t": b.time, "sel": list(b.selected_layers()),
            "playing": b.play.playing}


def _key(win, k, mods=None):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    QTest.keyClick(win, k, mods or Qt.KeyboardModifier.NoModifier)


def _type(win, text):
    from PySide6.QtCore import Qt
    for ch in text:
        key = {" ": Qt.Key.Key_Space, ".": Qt.Key.Key_Period}.get(ch) or Qt.Key(ord(ch.upper()))
        _key(win, key, Qt.KeyboardModifier.ShiftModifier if ch.isupper() else None)


def _click(win, item, x, y):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    p = item.mapToScene(QPointF(x, y)).toPoint()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)


def _items(win, test):
    out, todo = [], [win.contentItem() if hasattr(win, "contentItem") else win]
    while todo:
        o = todo.pop()
        if o.isVisible() and o.opacity() > 0:
            if test(o):
                out.append(o)
            todo.extend(o.childItems())
    return out


def _boxes(win):
    """Every editable kit box (FieldFrame) of the settings panel in view."""
    from PySide6.QtCore import QPointF
    sc = _items(win, lambda o: o.objectName() == "inspectorScroll")[0]
    top = sc.mapToScene(QPointF(0, 0)).y()
    inside = lambda o: top <= o.mapToScene(QPointF(0, 0)).y() and o.mapToScene(QPointF(0, o.height())).y() <= top + sc.height()
    return [o for o in _items(win, _is_box) if inside(o) and o.mapToScene(QPointF(0, 0)).x() > 1200]


def _is_box(o):
    return o.property("editable") is True and o.property("keepOnRefusal") is not None and o.property("commitSame") is not None


def test_keys_typed_into_any_box_stay_in_it(screen):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    b, win = screen
    C, S = Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.ShiftModifier
    b.select("title")
    from screen2d.steps import do_step
    do_step(b, win, "group Counter")                          # (setup) the counter's text boxes in view too
    QTest.qWait(400)
    boxes = _boxes(win)
    assert len(boxes) >= 6
    for box in boxes:                                         # a click on the box's padding, keys, Esc: nothing changes
        before = _state(b)
        _click(win, box, 3, 3)
        assert win.activeFocusItem() is not None and win.activeFocusItem().property("selectByMouse") is True, box
        _type(win, KEYS)
        for k in (Qt.Key.Key_Backspace, Qt.Key.Key_Home, Qt.Key.Key_Delete):
            _key(win, k)
        _key(win, Qt.Key.Key_A, C)
        _key(win, Qt.Key.Key_Escape)
        QTest.qWait(50)
        assert _state(b) == before, box

    before = _state(b)                                        # the time box (Alt+Shift+J): letters and Space stay in it
    _key(win, Qt.Key.Key_J, Qt.KeyboardModifier.AltModifier | S)
    _type(win, KEYS)
    _key(win, Qt.Key.Key_Escape)
    QTest.qWait(50)
    assert _state(b) == before

    row = _items(win, lambda o: o.objectName() == "row:countSuffix")[0]
    suffix = next(o for o in _items(row, _is_box))
    _click(win, suffix, 3, 3)                                 # "." typed first into an empty box goes into it (row 8)
    _type(win, ".40")
    _key(win, Qt.Key.Key_Return)
    QTest.qWait(50)
    assert ".40" in json.dumps(b.doc.item("title"))

    b._select(["card", "lockup"])                             # F2 right after Ctrl+G names the new group at once
    QTest.qWait(300)
    _key(win, Qt.Key.Key_G, C)
    _key(win, Qt.Key.Key_F2)
    _type(win, "Home list")
    _key(win, Qt.Key.Key_A, C)                                # Ctrl+A in the name box picks its words, not every layer
    _type(win, "Hm list")
    _key(win, Qt.Key.Key_Return)
    QTest.qWait(300)
    group = b.selected_layers()
    assert len(group) == 1 and b.doc.item(group[0]).get("name").lower() == "hm list"     # (a test key's words are lower case)
    assert not b.doc.item(group[0]).get("scaleX", 1) < 0 and not b.comp().get("markers") and not b.play.playing

    _key(win, Qt.Key.Key_Escape)                              # F2 right after drawing a shape names it
    _key(win, Qt.Key.Key_R)
    st = _items(win, lambda o: o.objectName() == "stage")[0]
    from PySide6.QtCore import QPointF
    a, z = st.mapToScene(QPointF(200, 200)).toPoint(), st.mapToScene(QPointF(320, 300)).toPoint()
    QTest.mousePress(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, a)
    QTest.mouseMove(win, z)
    QTest.mouseRelease(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, z)
    _key(win, Qt.Key.Key_F2)
    _type(win, "mid reef")
    _key(win, Qt.Key.Key_Return)
    QTest.qWait(300)
    made = b.selected_layers()
    assert len(made) == 1 and b.doc.item(made[0]).get("name") == "mid reef"
    assert not b.comp().get("markers") and not b.play.playing
