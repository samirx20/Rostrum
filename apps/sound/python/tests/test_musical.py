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


def test_typed_times_that_do_not_exist_are_refused():
    """KNOWN to matter: a typed beat the bar does not have used to be taken as a later beat (9.9.9 = beat 40)."""
    import pytest
    root = _doc().data
    for bad in ("5.9", "1.5", "2.1.960"):
        with pytest.raises(ValueError, match="beat|ticks"):
            musical.parse(bad, root)
    assert musical.parse("1.4", root) == musical.parse("1.4.0", root)


def test_note_length_in_note_values():
    """A note's length reads as a note value when it is one (0.1 read as nothing); the same words type back."""
    root = {"tempo": 120, "meter": "4/4"}
    from rostrum_sound.doc import musical as M
    for words, sec in (("1/4", 0.5), ("1/8", 0.25), ("1/16", 0.125), ("dotted 1/4", 0.75), ("1/1", 2.0)):
        assert M.note_length(sec, root) == words and abs(M.parse(words, root, True) - sec) < 1e-6
    assert M.note_length(0.3, root) == M.length(0.3, root)       # not a note value: bars.beats.ticks
