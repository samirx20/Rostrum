"""The lanes draw their selected outlines from the selection by row (select_slots.pickRows, read through Picks.js once
per pickStamp): what would break silently is a lane outlining another row's notes, or a lane keeping old outlines
because the stamp didn't move."""
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.bridge import SoundBridge  # noqa: E402
from test_screen import FakeEngine  # noqa: E402

SRC = '''
tempo(120); beats_per_bar(4)
lead = track("lead", builtIn="feltPiano")
lead.note("C4", at=beat(4), dur=beats(1))
lead.note("E4", at=beat(6), dur=beats(1))
bass = track("bass", builtIn="feltPiano")
bass.note("C2", at=beat(4), dur=beats(1))
'''


@pytest.fixture
def bridge(monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SRC, "song.py"))
    b = SoundBridge(doc)
    yield b
    b.close()


def test_each_row_gets_only_its_own_picks_and_the_stamp_follows(bridge):
    b = bridge
    notes = {r["id"]: [x["id"] for x in r["blocks"]] for r in b.rows_now() if r["id"] in ("lead", "bass")}
    s0 = b.pickStamp
    b.pickMany([notes["lead"][1], notes["bass"][0]])
    assert b.pickRows() == {"lead": [notes["lead"][1]], "bass": [notes["bass"][0]]}
    s1 = b.pickStamp
    assert s1 != s0                                     # a new selection: every lane reads its picks again
    b.doc.apply([{"op": "note.duplicate", "target": [notes["lead"][0]], "args": {"by": {"beats": 8}}}], b.who)
    assert b.pickStamp == s1                            # an edit that leaves the picks where they were: no re-read
    b.pickMany([])
    assert b.pickRows() == {} and b.pickStamp != s1
