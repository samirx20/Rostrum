"""A scrub's pictures are the moving kind (one blur step, half size); when it rests the full frame is asked again, once.
If the rest never came, the paused canvas would silently stay a cheaper picture than the export (preview ≡ export)."""
import sys
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screen2d import playback  # noqa: E402


class FakeBridge(QObject):
    def __init__(self):
        super().__init__()
        self.rests, self.time = 0, 0.0

    def comp(self):
        return {"fps": 25, "duration": 4.0, "width": 1920, "height": 1080}

    def time_rests(self):
        self.rests += 1


def settle():
    end = time.perf_counter() + (playback.SETTLE_MS + 150) / 1000
    while time.perf_counter() < end:
        QCoreApplication.processEvents()
        time.sleep(0.005)


def test_one_jump_is_full_a_scrub_moves_then_rests_full():
    app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841
    b = FakeBridge()
    p = playback.Playback(b)
    assert p.moved_by_hand() is False and p.samples() is None      # one jump: drawn full at once, nothing to rest
    assert p.moved_by_hand() is True and p.samples() == 1          # a second move soon after: a scrub
    p.moved_by_hand()
    settle()
    assert b.rests == 1 and not p.scrubbing and p.samples() is None  # rested: the full frame, asked once
