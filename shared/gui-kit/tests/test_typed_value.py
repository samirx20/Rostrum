"""A typed value lands on the item it was typed for: typing not yet entered, then another item picked, edits the first
item only (pending.py, FieldFrame, the bridge's held items)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from rostrum_core import toy

from rostrum_gui import DocBridge
from rostrum_gui.app import free, stop

KIT_QML = Path(__file__).resolve().parents[1] / "qml"
PANEL = b"""
import QtQuick
import QtQuick.Window
import RostrumKit
Window { width: 420; height: 900; visible: true
         Inspector { anchors.fill: parent; bridge: theBridge } }
"""


def _find(root, hit):
    stack = [root]
    while stack:
        it = stack.pop()
        if hit(it):
            return it
        stack.extend(it.childItems())
    return None


def _field(root, param):
    row = _find(root, lambda it: it.objectName() == f"row:{param}")
    field = row and _find(row, lambda it: it.property("pending") is not None)    # a kit field's text box (FieldFrame)
    assert field is not None, f"no field for {param}"
    return field


def test_typing_then_picking_another_item_edits_the_first_only():
    app = QGuiApplication.instance() or QGuiApplication([])
    bridge = DocBridge(toy.sample())
    bridge.select("title")
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(KIT_QML))
    ctx = engine.rootContext()
    for name, value in (("uiFont", "Arial"), ("monoFont", "Consolas"), ("theBridge", bridge)):
        ctx.setContextProperty(name, value)
    engine.loadData(PANEL, QUrl.fromLocalFile(str(KIT_QML / "typed_test.qml")))
    window = engine.rootObjects()[0]
    window.requestActivate()
    app.processEvents()
    field = _field(window.contentItem(), "x")
    field.forceActiveFocus()
    field.setProperty("text", "42")                     # typed, not entered
    app.processEvents()
    bridge.select("card")
    app.processEvents()
    assert bridge.doc.item("title")["x"] == 42
    assert bridge.doc.item("card")["x"] == 0
    assert len(bridge.doc.history.changes) == 1         # one undo step
    stop(engine, window, then=lambda: free(bridge))     # the window first, then what its bindings read


def test_a_held_field_keeps_its_items_and_drops_the_gone_ones():
    """The rule the 2D Key block shares (hold_ids / held_ids): items held for a field stay its targets whatever is picked
    later; one that is gone leaves the list (apps/2d/screen/tests/test_key_typed.py has the key case)."""
    bridge = DocBridge(toy.sample())
    bridge.hold_ids("key.value", ["title"])
    assert bridge.held_ids("key.value", ["card"]) == ["title"]
    assert bridge.held_ids("key.time", ["card"]) == ["card"]            # another field has its own
    bridge.hold_ids("key.value", ["title", "nothing"])
    assert bridge.held_ids("key.value", ["card"]) == ["title"]
    free(bridge)
