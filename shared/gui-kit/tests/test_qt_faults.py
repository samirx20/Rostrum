"""A QML TypeError / ReferenceError is a fault (qt_faults.py): a dead button must fail a scripted run, not print and go on."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine

from rostrum_gui import qt_faults


def _run(monkeypatch, body):
    monkeypatch.setenv("ROSTRUM_REAL_HOME", "1")            # a person's run: logged, the app is not ended
    QGuiApplication.instance() or QGuiApplication([])
    qt_faults.watch()
    before = len(qt_faults.found())
    engine = QQmlEngine()
    comp = QQmlComponent(engine)
    comp.setData(f"import QtQml\nQtObject {{ Component.onCompleted: {{ {body} }} }}".encode(), QUrl("test.qml"))
    comp.create()
    return qt_faults.found()[before:]


def test_a_qml_type_error_is_a_fault(monkeypatch):
    seen = _run(monkeypatch, "var x = null; x.go()")
    assert seen and "TypeError" in seen[0]


def test_a_qml_reference_error_is_a_fault(monkeypatch):
    seen = _run(monkeypatch, "nothingCalledThis.go()")
    assert seen and "ReferenceError" in seen[0]
