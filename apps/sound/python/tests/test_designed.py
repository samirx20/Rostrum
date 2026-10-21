"""Designed sounds: a script re-run (the motion score made again) keeps a person's edit to a sound, and a value
inside the shared field's range but outside its design's own is refused, never passed on."""
import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum_sound import KIND, compile, run_source

SCORE = """
ui = track("ui")
ui.sound("whoosh", at=1.0, dur=0.6, speed=[[0, 0], [0.3, 1], [1, 0]], panPath=[[0, -0.8], [1, 0.2]], brightness=0.5)
ui.sound("click", at=1.6, material=0.3, pitch=2000)
"""


def test_rerun_keeps_a_persons_edit_to_a_sound():
    doc = Document.new(KIND)
    doc.run_script("score.py", run_source(SCORE, "score.py"), Who.script("score.py"))
    doc.apply({"op": "sound.set", "target": ["ui.whoosh1000"], "args": {"brightness": 0.9}}, Who.person())
    doc.run_script("score.py", run_source(SCORE.replace("pitch=2000", "pitch=2400"), "score.py"), Who.script("score.py"))
    assert doc.item("ui.whoosh1000")["brightness"] == 0.9
    assert doc.item("ui.click1600")["pitch"] == 2400
    whoosh, click = compile(doc)["tracks"][0]["sounds"]
    assert whoosh["design"] == "whoosh" and whoosh["speed"][1] == [0.3, 1] and click["at"] == 1.6


def test_a_value_outside_its_designs_own_range_is_refused():
    doc = Document.new(KIND)
    with pytest.raises(RostrumError, match="outside 100 … 12000 for a click"):
        doc.run_script("s.py", run_source('track("ui").sound("click", at=0, pitch=60)', "s.py"), Who.script("s.py"))
    with pytest.raises(RostrumError, match="only applies when"):
        run_source('track("ui").sound("click", at=0, dur=0.5)', "s.py")
