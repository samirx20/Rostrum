"""meta.class_name lets go of a QML-made item's own metaobject, so a Qt object made later at its address never comes
back to Python as a QMetaObject; a built-in class's shared metaobject keeps working."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import shiboken6  # noqa: E402
from PySide6.QtCore import QByteArray  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402
from PySide6.QtQuick import QQuickItem  # noqa: E402

from rostrum_gui.meta import class_chain, class_name, has_property  # noqa: E402


def test_qml_metaobject_is_let_go_and_builtin_kept():
    QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlEngine()
    comp = QQmlComponent(engine)
    comp.setData(QByteArray(b"import QtQuick\nItem { property int extra: 1 }"), "")
    item = comp.create()
    assert "_QML" in class_name(item) and has_property(item, "extra")
    filed = [w for w in shiboken6.getAllValidWrappers() if type(w).__name__ == "QMetaObject" and "_QML" in w.className()]
    assert not filed, "a QML item's own metaobject stayed filed under its address"
    assert class_chain(item)[-2:] == ["QQuickItem", "QObject"]
    plain = QQuickItem()
    assert class_name(plain) == "QQuickItem"
    assert QQuickItem.staticMetaObject.className() == "QQuickItem", "the shared metaobject was let go"
