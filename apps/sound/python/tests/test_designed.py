"""Designed sounds: a script re-run keeps a person's edit to a sound, a value inside the shared field's range but
outside its design's own is refused, never passed on, and an old song with a whoosh (no longer made) still opens
with the whoosh named as a problem (the engine refuses to render it: contract/tests.rs)."""
import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum_sound import KIND, compile, run_source

SCORE = """
ui = track("ui")
ui.sound("riser", at=1.0, dur=0.6, brightness=0.5)
ui.sound("click", at=1.6, material=0.3, pitch=2000)
"""


def test_rerun_keeps_a_persons_edit_to_a_sound():
    doc = Document.new(KIND)
    doc.run_script("score.py", run_source(SCORE, "score.py"), Who.script("score.py"))
    doc.apply({"op": "sound.set", "target": ["ui.riser1000"], "args": {"brightness": 0.9}}, Who.person())
    doc.run_script("score.py", run_source(SCORE.replace("pitch=2000", "pitch=2400"), "score.py"), Who.script("score.py"))
    assert doc.item("ui.riser1000")["brightness"] == 0.9
    assert doc.item("ui.click1600")["pitch"] == 2400
    riser, click = compile(doc)["tracks"][0]["sounds"]
    assert riser["design"] == "riser" and riser["dur"] == 0.6 and click["at"] == 1.6


def test_a_value_outside_its_designs_own_range_is_refused():
    doc = Document.new(KIND)
    with pytest.raises(RostrumError, match="outside 100 … 12000 for a click"):
        doc.run_script("s.py", run_source('track("ui").sound("click", at=0, pitch=60)', "s.py"), Who.script("s.py"))
    with pytest.raises(RostrumError, match="only applies when"):
        run_source('track("ui").sound("click", at=0, dur=0.5)', "s.py")


def test_an_old_song_with_a_whoosh_opens_and_names_it(tmp_path):
    doc = Document.new(KIND, folder=str(tmp_path), item="song")
    doc.run_script("s.py", run_source(SCORE, "s.py"), Who.script("s.py"))
    doc.save()
    for f in (tmp_path / "docs").glob("song.*"):   # the saved song, as written before whooshes were removed
        text = f.read_text(encoding="utf-8")
        f.write_text(text.replace('"design":"riser"', '"design":"whoosh"').replace('"design": "riser"', '"design": "whoosh"'), encoding="utf-8")
    from rostrum_sound.opening import open_whole
    old = open_whole(str(tmp_path), "song")
    assert old.item("ui.riser1000")["design"] == "whoosh"
    assert "ui.riser1000: this song has a whoosh, which Rostrum no longer makes; remove it or replace it" in old.notes
