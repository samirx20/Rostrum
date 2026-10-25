"""What the player relies on: a render that is not a whole WAV (empty, cut short) is refused loudly and never loaded."""
import sys
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screensound import playback  # noqa: E402
from screensound.wholewav import is_whole_wav  # noqa: E402
from test_screen import FakeEngine  # noqa: E402


class Cut(FakeEngine):
    def request(self, do, schedule=None, out=None, **kw):
        reply = super().request(do, schedule, out, **kw)
        Path(out).write_bytes(Path(out).read_bytes()[:-10])     # the file ends before its header says
        return reply


def test_a_cut_short_render_is_refused_and_never_reaches_the_player(tmp_path, monkeypatch):
    QCoreApplication.instance() or QCoreApplication([])
    whole = tmp_path / "w.wav"
    FakeEngine().request("render", out=str(whole))
    assert is_whole_wav(whole)
    monkeypatch.setattr(playback, "open_engine", Cut)
    r, got, said = playback.Renderer(), [], []
    r.rendered.connect(got.append)
    r.failed.connect(said.append)
    try:
        r.request({})
        for _ in range(100):
            QCoreApplication.processEvents()
            if r.idle() and (got or said):
                break
            time.sleep(0.05)
        QCoreApplication.processEvents()
        assert not got and said and "is not a whole WAV" in said[0]
    finally:
        r.close()
