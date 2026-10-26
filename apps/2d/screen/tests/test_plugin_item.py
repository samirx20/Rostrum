"""A plugin's item (a kind with a colon, "wiggle:generator") that this Rostrum can't read is a plain row on the screen:
a person can lock, hide, move and delete it with real mouse and keys, each is one change that Ctrl+Z puts back, and
after a save and reopen every field inside it is exactly as the file had it. Needs the built engine."""
import json
import sys
import time
from pathlib import Path

import pytest
from rostrum2d import settings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

PART = {"id": "wig1", "type": "wiggle:generator", "wiggle:amount": 3, "wiggle:curve": {"pts": [[0, 1.5], [1, None]], "name": "ü "},
        "seed": [1, [2, {"a": True}]], "odd": 1e-7, "name": "Wiggler"}
ANIMS = 'shape("a", w=100, h=60, fill="#336699", x=100, y=200)\nshape("b", w=100, h=60, fill="#996633", x=300, y=200)\n'


def test_a_plugin_item_locks_hides_moves_deletes_and_keeps_its_insides(tmp_path):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtTest import QTest
    from rostrum_core import Document
    from rostrum_core.storage import paths
    from rostrum2d import KIND, run_source
    from rostrum_gui.app import qt_app
    from screen2d.session import Session
    app = qt_app()
    d = Document.new(KIND, folder=str(tmp_path), item="proj")
    d.run_script("a.py", run_source('comp("main", name="Main", width=1920, height=1080, fps=30, duration=4)\n' + ANIMS, "a.py"))
    d.save()
    p = paths(tmp_path, "proj", KIND.ext)["doc"]
    f = json.loads(p.read_text(encoding="utf-8"))
    f["doc"]["comps"][0]["layers"].insert(1, json.loads(json.dumps(PART)))
    p.write_text(json.dumps(f), encoding="utf-8")
    session = Session((1646, 900), None)
    session.files.put(Document.open(tmp_path, "proj", KIND))
    QTest.qWait(1500)
    b, win = session.bridge, session.win
    slow = []

    def named(name):
        todo = [win.contentItem()]
        while todo:
            o = todo.pop()
            if o.objectName() == name:
                return o
            todo.extend(o.childItems())

    def item():
        return dict(b.doc.item("wig1")) if b.doc.has("wig1") else None

    def settle(fn):                                   # a pointer action: the change lands within a screen refresh or so
        t = time.perf_counter()
        fn()
        slow.append((time.perf_counter() - t) * 1000)
        QTest.qWait(250)

    def click_switch(field):
        sw = named(f"layerSwitch:wig1:{field}")
        assert sw is not None, f"the {field} switch on the plugin item's row is missing"
        QTest.mouseMove(win, QPoint(100, int(sw.mapToScene(QPointF(9, 9)).y())))
        QTest.qWait(250)
        win.grabWindow()
        sw = named(f"layerSwitch:wig1:{field}")
        q = sw.mapToScene(QPointF(9, 9)).toPoint()
        settle(lambda: QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, q))

    def row_point(i):
        n = named(f"layerSwitch:{i}:locked")
        return n.mapToScene(QPointF(-60, 9)).toPoint()      # the row's name, left of its switches

    try:
        win.grabWindow()
        assert item() == PART and any(r["id"] == "wig1" for r in b.layers)
        for field in ("locked", "hidden"):
            click_switch(field)
            assert item() == {**PART, field: True}, field
            QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
            QTest.qWait(250)
            assert item() == PART, field + " undone"
        # move: drag its name onto another layer's row
        order = lambda: [c["id"] for c in b.doc.item(b.comp_id)["layers"]]   # noqa: E731
        before = order()
        rows = [r["id"] for r in b.layers if r["row"] == "layer" and not r.get("frame")]
        other = next(i for i in rows if i != "wig1")
        a, z = row_point("wig1"), row_point(other)
        QTest.mouseMove(win, a)
        QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, a)
        for n in range(1, 11):
            q = QPoint(a.x(), int(a.y() + (z.y() - a.y()) * n / 10 + (8 if z.y() > a.y() else -8)))
            QTest.mouseMove(win, q)
            QTest.qWait(16)
        t = time.perf_counter()
        QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, q)
        slow.append((time.perf_counter() - t) * 1000)
        QTest.qWait(250)
        assert order() != before and item() == PART
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
        QTest.qWait(250)
        assert order() == before
        # delete: pick its row, press Delete
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, row_point("wig1"))
        QTest.qWait(250)
        assert "wig1" in b.selection
        settle(lambda: QTest.keyClick(win, Qt.Key_Delete))
        assert item() is None
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
        QTest.qWait(250)
        assert item() == PART
        win.grabWindow()
        QTest.qWait(300)
        win.grabWindow()
        # lock it for good, save, reopen: everything inside is as it was
        click_switch("locked")
        b.doc.save()
        again = json.loads(p.read_text(encoding="utf-8"))["doc"]["comps"][0]["layers"]
        saved = next(x for x in again if x["id"] == "wig1")
        assert {k: v for k, v in saved.items() if k != "locked"} == PART
        reopened = Document.open(tmp_path, "proj", KIND)
        assert {k: v for k, v in reopened.item("wig1").items() if k != "locked"} == PART
        print("pointer actions (ms):", [round(x, 1) for x in slow])
        assert max(slow) < 120, slow
    finally:
        app.processEvents()
        session.close()
