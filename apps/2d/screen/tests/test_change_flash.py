"""The change outline after an undo or an agent's change (change_flash.py): no box while the picture on screen is still
the old one (it sat in the old place ~250 ms), the box where the new picture shows the layer once it lands, and no
news while nothing changes (a frame that changes nothing never starts the outline's fade again). No window."""
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class Agent(QObject):
    changed = Signal()
    flash = []


class Bridge(QObject):
    shownChanged = Signal()

    def __init__(self):
        super().__init__()
        self.agent, self.fresh, self.box = Agent(self), True, {"x": 0, "w": 10}

    def shows_now(self):
        return self.fresh

    def rectOf(self, item_id):
        return dict(self.box) if item_id == "a" else {}


def test_outline_waits_for_the_picture_that_shows_the_change():
    from rostrum_gui.app import qt_app
    from screen2d.change_flash import ChangeFlash
    qt_app()
    b = Bridge()
    flash = ChangeFlash(b)
    told = []
    flash.changed.connect(lambda: told.append(flash.boxes))

    b.fresh, b.agent.flash = False, ["a", "gone"]       # the undo: the picture on screen is still the old one
    b.agent.changed.emit()
    assert flash.boxes == [] and told == []

    b.fresh, b.box = True, {"x": 50, "w": 10}            # the new picture lands: the box where it now shows
    b.shownChanged.emit()
    assert flash.boxes == [{"x": 50, "w": 10, "id": "a"}]

    b.shownChanged.emit()                                # another frame, nothing changed: no news, the fade runs on
    assert len(told) == 1

    b.agent.flash = []                                   # the second is over
    b.agent.changed.emit()
    assert flash.boxes == []
