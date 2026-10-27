"""Every test starts with no window of an earlier test still alive: a window left open (closed but not yet deleted)
counts as one that draws, so work waiting for "the next frame" (after_frame.py) waits for it instead of running at
once, and a later test that reads straight after a pick saw the old panel (test_effects after the QML tests); and the
last key of a test (pointer_quiet.acted) never makes the next test's pick wait for a quiet moment (test_actions then
test_effects failed on main too, run alone)."""
import pytest


@pytest.fixture(autouse=True)
def _no_windows_left():
    yield
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtGui import QGuiApplication
    if not isinstance(QCoreApplication.instance(), QGuiApplication):
        return
    for w in QGuiApplication.topLevelWindows():
        w.close()
        w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QCoreApplication.processEvents()
    from rostrum_gui import pointer_quiet
    for w in pointer_quiet._watch.values():
        w.last = 0.0
