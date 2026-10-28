"""A script lands on a time by its marker name (3E audit B8): downbeat / land / seconds_of read "#name" through the one
marker reader, marker(shared=True) reaches the project's markers (2D follows them), and a script written all in
seconds is told a tempo change won't move it. A miss here puts the music off the picture without a word."""
from types import SimpleNamespace

import pytest
from rostrum_core import Document, RostrumError, Who
from rostrum_core import markers as project

from rostrum_sound import KIND, compile, run_source
from rostrum_sound.doc import markers, tempo
from rostrum_sound.mcp import script_shared
from rostrum_sound.script_scope import printed


def test_a_one_letter_marker_keeps_its_offset():
    assert markers.parts("#b+0.5") == ("b", 0.5, "s") and markers.parts("#a-2beats") == ("a", -2.0, "beats")
    assert markers.parts("#big-hit-1") == ("big-hit", -1.0, "s") and markers.parts("#logo lands") == ("logo lands", 0.0, "s")


def test_downbeat_and_land_take_a_marker_name_and_say_the_seconds():
    tree = run_source('tempo(120); marker("logo lands", at=4.0); downbeat(bar(3), at="#logo lands" + beats(1))', "a.py")
    assert tempo.seconds_at(tree, 8.0) == pytest.approx(4.5)
    assert any("4.5 s" in line and "#logo lands+1beats" in line for line in printed())
    tree = run_source('tempo(120); length(bar(12)); marker("a", at=16.3); land(bar(9), at="#a", ramp_from=bar(5))', "b.py")
    assert tempo.seconds_at(tree, 32.0) == pytest.approx(16.3, abs=1e-6)


def test_seconds_of_a_marker_and_a_section_between_markers():
    tree = run_source('tempo(120); marker("a", at=2.0); marker("b", at=bar(3)); length(10)\n'
                      'section("v", "#a", "#b+0.5"); print(seconds_of("#b+0.5"))', "c.py")
    assert tree["sections"][0]["end"] == "#b+0.5" and printed() == ["4.5"]


def test_a_tempo_change_wont_move_music_written_in_seconds_is_said():
    run_source('t = track("k", builtIn="piano")\nfor i in range(10): t.note("C4", at=i * 0.5, dur=0.4)', "d.py")
    assert any("all 10 notes and hits are in seconds" in line for line in printed())
    run_source('t = track("k", builtIn="piano")\nfor i in range(10): t.note("C4", at=beat(i), dur=0.4)', "e.py")
    assert not any("in seconds" in line for line in printed())


SHARED = 'tempo(120); marker("logo", at=bar(3), shared=True)\nt = track("k", builtIn="piano"); t.note("C4", at="#logo", dur=1)'


def _ctx(folder):
    notes = []
    return SimpleNamespace(app=SimpleNamespace(folder=folder), who=Who.script("s.py"), note=notes.append, notes=notes)


def test_a_shared_marker_is_published_to_the_project_and_the_song_follows_it(tmp_path):
    doc, ctx = Document.new(KIND, folder=tmp_path, item="song"), _ctx(tmp_path)
    with markers.project(tmp_path):
        script_shared.publish(ctx, doc, {"source": SHARED, "name": "s.py"})
        assert [(m["name"], m["at"]) for m in project.listing(tmp_path)] == [("logo", 4.0)]
        doc.run_script("s.py", run_source(SHARED, "s.py", doc), Who.script("s.py"))
        assert doc.data["markers"] == [] and compile(doc)["tracks"][0]["notes"][0]["at"] == 4.0
        script_shared.publish(ctx, doc, {"source": SHARED, "name": "s.py"})     # again: the same marker, nothing new
        assert len(project.listing(tmp_path)) == 1 and len(ctx.notes) == 1
        mid = project.listing(tmp_path)[0]["id"]
        project.edit(tmp_path, [{"op": "marker.move", "target": [mid], "args": {"at": 6.0}}], Who.person())
        assert compile(doc)["tracks"][0]["notes"][0]["at"] == 6.0                 # 2D moved it: the note follows
        with pytest.raises(RostrumError, match="logo"):                           # the script's own time now differs
            script_shared.publish(ctx, doc, {"source": SHARED, "name": "s.py"})
