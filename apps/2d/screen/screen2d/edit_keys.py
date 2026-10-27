"""`edittime typed | ctrlz` (edit_steps.py): an edit and an undo made with a person's real keys (QTest on the window),
never a bridge slot: the X field ("row:x", the visible one) is clicked, its text selected (Ctrl+A), the number typed,
then Enter; an undo is a real Ctrl+Z on the window. Each fails loudly when the keys did not make the change.
A real window kept behind the person's work (ROSTRUM_BACKGROUND_WINDOWS) is never the focus window, and Qt's shortcut
map gives Ctrl+Z only to that one: run `ctrlz` offscreen (QT_QPA_PLATFORM=offscreen), where the window has the focus."""
from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, QPointF, Qt
from PySide6.QtGui import QGuiApplication
from rostrum_gui.lazy_qtest import QTest   # never at import: a person's launch must not count as scripted (lazy_qtest.py)

from .click_steps import _named


def _typed(bridge, value):
    """Type `value` into the visible X field as a hand does: click in it, select all, the digits (not yet Enter)."""
    win = next(w for w in QGuiApplication.topLevelWindows() if w.findChild(QObject, "stage"))
    row = _named(win, "row:x")
    box = next((o for o in _items(row) if o.metaObject().className().startswith("QQuickTextInput")), None) if row else None
    if box is None:
        raise RuntimeError("edittime typed: no visible X field (row:x) to type in")
    q = box.mapToScene(QPointF(box.property("width") / 2, box.property("height") / 2))
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(round(q.x()), round(q.y())))
    QTest.keyClick(win, Qt.Key_A, Qt.ControlModifier)
    for ch in str(value):                       # one key per digit (QTest has no typing of text into a window)
        QTest.keyClick(win, Qt.Key(ord(ch)))
    return win


def _items(item):
    todo = [item]
    while todo:
        o = todo.pop()
        yield o
        todo.extend(o.childItems())


def keys(bridge, kind):
    """typed / ctrlz: (setup, the timed real key, undo steps a repetition leaves)."""
    held = {}

    def type_in(i):
        held["win"] = _typed(bridge, 760 + 40 * (i % 2 + 1))
        held["data"] = bridge.doc.data

    def enter(i):
        QTest.keyClick(held["win"], Qt.Key_Return)
        if bridge.doc.data is held["data"]:
            raise RuntimeError(f"edittime typed: Enter in the X field made no change ({bridge.status})")
    if kind == "typed":
        return type_in, enter, 1

    def typed_whole(i):
        type_in(i)
        enter(i)
        held["data"] = bridge.doc.data

    def ctrl_z(i):
        QTest.keyClick(held["win"], Qt.Key_Z, Qt.ControlModifier)
        if bridge.doc.data is held["data"]:
            raise RuntimeError(f"edittime ctrlz: Ctrl+Z on the window took nothing back ({bridge.status}; a window kept "
                               "behind never gets shortcuts: run it offscreen)")
    return typed_whole, ctrl_z, 0


def slide_time(bridge, n=10, layer="card", param="opacity"):
    """`edittime slide [n] [layer=<id>]`: a real mouse drag (QTest) on the visible slider of `param` (Opacity): press
    on it, 8 moves a screen refresh apart, release. Screen-thread busy ms of the press, the first move (its frame), the
    later moves and the release (until the screen rests: the finished edit, its picture). Each drag is undone after."""
    import statistics
    from .drag_steps import Busy, _wait
    bridge.select(layer)
    _wait(400)
    win = next(w for w in QGuiApplication.topLevelWindows() if w.findChild(QObject, "stage"))
    row = _named(win, f"row:{param}")
    sl = next((o for o in _items(row) if "Slider" in o.metaObject().className()), None) if row else None
    if sl is None:
        raise RuntimeError(f"edittime slide: no visible slider on row:{param}")
    busy, out = Busy(), {"press": [], "first": [], "moves": [], "release": []}

    def at(f):
        q = sl.mapToScene(QPointF(sl.property("width") * f, sl.property("height") / 2))
        return QPoint(round(q.x()), round(q.y()))

    def timed(key, fn, rest_ms):
        b0 = busy.now()
        fn()
        _wait(rest_ms)
        out[key].append(busy.now() - b0)
    try:
        for i in range(n):
            a, z = (0.3, 0.7) if i % 2 == 0 else (0.7, 0.3)
            data = bridge.doc.data
            QTest.mouseMove(win, at(a))
            _wait(150)
            timed("press", lambda: QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, at(a)), 16)
            for k in range(1, 9):
                p = at(a + (z - a) * k / 8)
                timed("first" if k == 1 else "moves", lambda: QTest.mouseMove(win, p), 16)
            timed("release", lambda: QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, at(z)), 300)
            if bridge.doc.data is data:
                raise RuntimeError("edittime slide: the drag on the slider changed nothing")
            bridge.undo()
            _wait(300)
    finally:
        busy.close()
    med = lambda v: f"{statistics.median(v):.1f}/{max(v):.1f}"     # noqa: E731
    print(f"edittime slide: n={n}; busy median/worst ms: press {med(out['press'])}; first move {med(out['first'])}; "
          f"later moves {med(out['moves'])}; release {med(out['release'])}")
