"""Esc closes the newest open popup, dialog or sheet from ONE place (AppShell's Esc and OpenPopups), wherever the
keyboard is: a plain menu, a modal dialog, a dropdown inside a modal dialog (a dialog's scrim stops the window's own
shortcuts), a side menu and then its menu (one level per press), and a sheet that is not a popup (History). Every one
here is opened without giving it the keyboard, as a click on a menu entry leaves it (the bug: Esc did nothing)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["ROSTRUM_BACKGROUND_WINDOWS"] = "1"

from PySide6.QtCore import QMetaObject, QObject, Q_ARG, Qt
from PySide6.QtTest import QTest
from rostrum_core import toy

from rostrum_gui import DocBridge
from rostrum_gui.app import start, stop
from rostrum_gui.pointer import wait_until

WINDOW = """
import QtQuick
import RostrumKit
AppShell {
    bridge: theBridge; helpEntries: []
    centre: Item {
        anchors.fill: parent
        Menu { objectName: "plain"; entries: [{ value: "a", label: "A" }] }
        SmallPopup { objectName: "dialog"; modal: true; width: 300; height: 200
                     ChoiceField { objectName: "choice"; width: 160; options: ["one", "two"]; current: "one" } }
        ActionMenu { objectName: "menu"
                     entries: [{ value: "x", label: "X" }, { value: "s", label: "Sub", sub: [{ value: "s1", label: "S1" }] }] }
    }
}
"""


def _esc(win, obj, prop="opened"):
    """Esc, then wait until `obj` reports closed (its state, not a fixed time)."""
    QTest.keyClick(win, Qt.Key_Escape)
    wait_until(lambda: not obj.property(prop), f"{obj.objectName() or obj} to close after Esc")


def _call(obj, name, *args, prop="opened"):
    QMetaObject.invokeMethod(obj, name, *[Q_ARG("QVariant", a) for a in args])
    wait_until(lambda: obj.property(prop), f"{obj.objectName() or obj} to open ({name})")


def test_esc_closes_the_newest_popup_wherever_the_keys_are(tmp_path):
    main = tmp_path / "Main.qml"
    main.write_text(WINDOW, encoding="utf-8")
    bridge = DocBridge(toy.sample())
    app, engine, win = start(main, {"theBridge": bridge}, (1200, 800))
    try:
        find = lambda name: win.findChild(QObject, name)      # noqa: E731
        plain, dialog, choice, menu = find("plain"), find("dialog"), find("choice"), find("menu")

        _call(plain, "open")
        assert plain.property("opened")
        _esc(win, plain)
        assert not plain.property("opened"), "Esc left a plain menu open"

        _call(dialog, "open")
        _call(choice, "open")                   # a dropdown inside a modal dialog
        assert choice.property("opened")
        _esc(win, choice)
        assert not choice.property("opened") and dialog.property("opened"), "Esc must close the dropdown first, only it"
        _esc(win, dialog)
        assert not dialog.property("opened"), "Esc left a modal dialog open"

        _call(menu, "openAt", 40, 40, 0)
        QMetaObject.invokeMethod(menu, "openSub", Q_ARG("QVariant", 1))
        subs = lambda: [m for m in win.findChildren(QObject) if m is not menu and m.property("owner") == menu]  # noqa: E731
        wait_until(lambda: subs() and subs()[0].property("opened"), "the side menu to open")
        sub = subs()
        _esc(win, sub[0])
        assert not sub[0].property("opened") and menu.property("opened"), "one Esc closes the side menu, not its menu"
        _esc(win, menu)
        assert not menu.property("opened"), "the second Esc closes the menu"

        _call(win, "openHistory", "", prop="historyOpen")
        assert win.property("historyOpen")
        _esc(win, win, "historyOpen")
        assert not win.property("historyOpen"), "Esc left the History sheet open"
    finally:
        stop(engine, win, then=bridge.deleteLater)
