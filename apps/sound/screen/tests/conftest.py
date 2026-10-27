"""Every Sound screen test plays through the player's stand-in (stand_in.FAKE_PLAYER), never the machine's speakers: a
test that sets its own (`player.program = …`) still does."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_sound.live_play import LivePlay  # noqa: E402
from stand_in import FAKE_PLAYER  # noqa: E402


@pytest.fixture(autouse=True)
def fake_player(monkeypatch):
    monkeypatch.setattr(LivePlay, "program", FAKE_PLAYER)


@pytest.fixture(autouse=True)
def windows_closed():
    """A test leaves no window behind, passed or failed: every Sound screen it made is closed (when the test did not),
    Qt's pending deletes run, and any other window it opened is closed. A window left open kept the keyboard and its
    items alive, and the next test's checks found them (test_roll_keeps_rows failed only in the full folder run)."""
    import main as soundmain
    import shiboken6
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtGui import QGuiApplication
    made, real = [], soundmain.Screen.__init__

    def init(self, *a, **k):
        real(self, *a, **k)
        made.append(self)
    soundmain.Screen.__init__ = init
    app = QGuiApplication.instance()
    key = lambda w: shiboken6.getCppPointer(w)[0]          # noqa: E731  (the window, not its Python wrapper)
    before = {key(w) for w in app.topLevelWindows()} if app is not None else set()
    try:
        yield
    finally:
        soundmain.Screen.__init__ = real
        for s in made:
            if s.engine is not None:
                s.close()
        app = QGuiApplication.instance()
        if app is not None:
            for _ in range(2):        # a close inside an event loop deletes on the loop's next turn (app.stop)
                QCoreApplication.processEvents()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            for w in app.topLevelWindows():
                if key(w) not in before and w.isVisible():
                    w.close()
