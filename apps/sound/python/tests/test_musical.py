"""Typed bars.beats must land where the formatter says, through a 6/8 change and a tempo glide, and an inspector edit
keeps the form the time was written in (beats stay beats, a marker stays a marker)."""
import sys
from pathlib import Path

from rostrum_core import Document, Who

from rostrum_sound import KIND, run_source
from rostrum_sound.doc import musical

sys.path.insert(0, str(Path(__file__).parents[2] / "screen"))
from screensound import inspect   # noqa: E402

SONG = """
tempo(100); beats_per_bar(4)
meter_change(bar(3), 6, 8); tempo_change(bar(5), 140, ramp=True); tempo_change(bar(7), 80)
marker("land", at=bar(2))
p = track("lead", builtIn="feltPiano")
p.note("D4", at=beat(9), dur=beats(2), id="a"); p.note("F4", at="#land+0.5", dur=1.0, id="m")
"""


def _doc():
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SONG, "song.py"), Who.script("song.py"))
    return doc


def test_typed_positions_round_trip():
    root = _doc().data
    for text in ("1.1", "2.3", "3.5", "4.6.480", "5.2", "6.3", "7.1", "8.2"):      # 6/8 from bar 3, glide bars 5-7
        assert musical.position(musical.parse(text, root), root) == text
    assert musical.parse("5", root) == musical.parse("5.1", root)
    assert abs(musical.parse("0:09.6", root) - 9.6) < 1e-9 and abs(musical.parse("9.6 s", root) - 9.6) < 1e-9
    assert musical.length(musical.parse("1.2", root, True, 5.0), root, 5.0) == "1.2"


def test_inspector_edit_keeps_the_form():
    doc = _doc()
    assert inspect.edit_call(doc, "a", "at", "3.1")["args"] == {"at": {"beat": 8.0}}          # beats stay beats
    assert inspect.edit_call(doc, "m", "at", "2.3")["args"] == {"at": "#land+1.2"}            # a marker stays a marker
    assert inspect.edit_call(doc, "a", "dur", "1.0")["args"] == {"dur": {"beats": 3.0}}       # a bar of 6/8
