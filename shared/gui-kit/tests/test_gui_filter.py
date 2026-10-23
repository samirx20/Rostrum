"""A Python error in an event filter is reported loudly and the app carries on (gui_filter.py, qt_faults.py)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QTimer
from PySide6.QtGui import QGuiApplication

from rostrum_gui import qt_faults
from rostrum_gui.gui_filter import GuiFilter


class Broken(GuiFilter):
    def on_event(self, obj, event):
        if event.type() == QEvent.Type.User:
            raise RuntimeError("broken filter")
        return False


def test_an_error_in_a_filter_is_reported_and_the_app_lives_on(monkeypatch, capfd):
    monkeypatch.setenv("ROSTRUM_REAL_HOME", "1")            # a person's run: logged, not ended
    app = QCoreApplication.instance() or QGuiApplication([])
    qt_faults.watch()
    target, before = QObject(), len(qt_faults.found())
    Broken(target).watch(target)
    later = []
    QTimer.singleShot(0, lambda: QCoreApplication.sendEvent(target, QEvent(QEvent.Type.User)))
    QTimer.singleShot(50, lambda: (later.append("alive"), app.exit(0)))
    assert app.exec() == 0 and later == ["alive"]
    assert "Broken.on_event" in qt_faults.found()[before] and "broken filter" in qt_faults.found()[before]
    assert "FAULT: Python error in Broken.on_event" in capfd.readouterr().err
