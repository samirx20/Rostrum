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
