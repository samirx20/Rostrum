"""Try before you keep (INTERACTION.md 1.21 rule 6): a choice only hovered in an amounts box shows on the work and goes
back when its list closes; a pick stays; Esc leaves no step; Enter keeps exactly one, with what was set (never a
choice that was only hovered)."""
from types import SimpleNamespace

from PySide6.QtCore import QCoreApplication
from rostrum_core import Param

from rostrum_gui.actions import Action
from rostrum_gui.amounts_page import AmountsPage

EASE = Param("ease", "choice", label="Ease", options=["linear", "in", "out"], default="linear")


class Drag:
    """A document drag: what it shows now (`shown`), and how it ended."""
    def __init__(self):
        self.shown, self.ended = None, None

    def fresh_calls(self, fn):
        return fn()

    def same(self, calls):
        return False

    def preview(self, calls, fresh=False):
        self.shown = calls[0]["args"]["ease"]

    def end(self, cancel=False, label=None):
        self.ended = "cancel" if cancel else label
        return None if cancel else SimpleNamespace(label=label)


def _page():
    _app = QCoreApplication.instance() or QCoreApplication([])
    drags = []
    page = AmountsPage(lambda label: drags.append(Drag()) or drags[-1], lambda change, label: None, lambda line: None)
    action = Action("ease", "Ease", amounts=("ease",), calls=lambda f, am: [{"op": "key.ease", "target": ["k1"],
                                                                         "args": {"ease": am.get("ease", "linear")}}])
    registry = SimpleNamespace(get=lambda op: SimpleNamespace(params=[EASE]))
    facts = SimpleNamespace(ids=["k1"], items=[{"id": "k1", "type": "key"}],
                            doc=SimpleNamespace(kind=SimpleNamespace(registry=registry)))
    page.open(action, facts, "Ease")
    return page, drags


def _settle(page):
    page._later.flush()


def test_hovered_choice_shows_then_goes_back_and_a_pick_stays():
    page, drags = _page()
    page.tryValue("ease", "in")
    _settle(page)
    assert drags[0].shown == "in"                 # resting on "in" shows it on the work
    page.untry()                                  # the list closed with no pick
    _settle(page)
    assert drags[0].shown == "linear"
    page.tryValue("ease", "out")
    page.setValue("ease", "out")                  # picked: the list then closes (untried) and the pick stays
    page.untry()
    _settle(page)
    assert drags[0].shown == "out"
    page.keep()
    assert drags[0].ended and "Ease" in drags[0].ended


def test_esc_records_nothing_and_enter_keeps_what_was_set_not_hovered():
    page, drags = _page()
    page.tryValue("ease", "in")
    page.cancel()
    assert drags[0].ended == "cancel"
    page, drags = _page()
    page.tryValue("ease", "out")                  # only hovered when Enter lands: not kept
    page.keep()
    assert drags[0].shown == "linear" and drags[0].ended not in (None, "cancel")


CHOICE = b"""
import QtQuick
import QtQuick.Controls
import RostrumKit
ApplicationWindow { width: 400; height: 400; visible: true
    property var picks: []
    property string lastTried: ""
    ChoiceField { objectName: "grid"; x: 20; y: 20; width: 160; height: 24
                  options: ["1/4", "1/8", "1/16"]; current: "1/16"
                  onTried: (v) => { lastTried = v; current = v }            // an amounts box shows the tried one in the field
                  onUntried: { if (lastTried !== "") current = "1/16"; lastTried = "" }
                  onPicked: (v) => { picks = picks.concat([v]); lastTried = ""; current = v } }
}
"""


def test_a_click_on_the_hovered_choice_is_kept(tmp_path):
    """Rest on a choice (it shows, tried), then pick that same choice: it is kept, never put back (member A's real-window
    find: a click on the hovered option was lost, since `current` already showed it)."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from rostrum_gui.pointer import hover, wait
    from rostrum_gui.app import start, stop
    main = tmp_path / "Main.qml"
    main.write_bytes(CHOICE)
    app, engine, win = start(main, {}, (400, 400))      # the kit's own start: a plain engine first breaks later windows
    wait(50)
    field = win.findChild(QQuickItem, "grid")
    c = field.mapToScene(field.boundingRect().center())
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, QPoint(int(c.x()), int(c.y())))
    wait(200)
    def items(it):
        for c in it.childItems():
            yield c
            yield from items(c)
    rows = win.findChild(QQuickItem, "choiceList")
    opt = next(t for t in items(rows) if t.property("text") == "1/8")
    p = opt.mapToScene(opt.boundingRect().center())
    at = QPoint(int(p.x()), int(p.y()))
    QTest.keyClick(win, Qt.Key_Up)                # ↑ rests on 1/8 (an offscreen window gets no hover in a popup)
    wait(30)
    assert win.property("lastTried") == "1/8" and field.property("current") == "1/8"
    QTest.keyClick(win, Qt.Key_Return)            # and picks it: kept, never put back by the list's close
    wait(300)
    assert list(win.property("picks").toVariant() if hasattr(win.property("picks"), "toVariant") else win.property("picks")) == ["1/8"]
    assert field.property("current") == "1/8"
    stop(engine, win)
