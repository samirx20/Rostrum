"""The script forms agents write first: beat arithmetic, drum names, plain Python, and the before-render checks."""
import json

import pytest

from rostrum_core import Document, RostrumError, Who
from rostrum_sound import run_source
from rostrum_sound.compile import compile
from rostrum_sound.doc import KIND
from rostrum_sound.mcp.app import make_app
from rostrum_sound.mcp.server import make_runtime
from rostrum_sound.script_scope import printed


def notes(src):
    return run_source("tempo(120); length(bar(9)); s = track('k', builtIn='grandPiano')\n" + src, "t.py")["tracks"][0]["notes"]


def server(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path))
    monkeypatch.setenv("ROSTRUM_SETTINGS_DIR", str(tmp_path / "settings"))
    (tmp_path / "engine.exe").write_bytes(b"")              # the engine starts on first use; never used here
    monkeypatch.setenv("ROSTRUM_SOUND_ENGINE", str(tmp_path / "engine.exe"))
    Document.new(KIND, folder=str(tmp_path / "song"), item="main").save()
    app = make_app(tmp_path / "song", ["main"])
    return app, make_runtime(app)


def test_beat_arithmetic_gives_plain_values_the_history_can_write(tmp_path, monkeypatch):
    src = "tempo(120); s = track('k', builtIn='grandPiano')\nfor i in range(2):\n    s.note('C4', at=bar(2) + i * beats(1), dur=beats(1) * 2)"
    n = run_source(src, "t.py")["tracks"][0]["notes"]
    assert [x["at"] for x in n] == [{"beat": 4}, {"beat": 5}] and n[0]["dur"] == {"beats": 2}
    assert notes("s.note('C4', at=beat(16) + 0, dur=1)")[0]["at"] == {"beat": 16}     # 0 is the same in beats and seconds
    doc = Document.new(KIND, folder=str(tmp_path / "plain"), item="main")
    doc.save()
    json.dumps(doc.run_script("t.py", run_source(src, "t.py"), Who.agent("t")).change.to_dict())
    app, rt = server(tmp_path, monkeypatch)
    try:                                                    # through the server; print lines come back
        reply, _ = rt.call("run_script", {"source": src + "\nprint('two notes')"}, Who.agent("tester"))
        assert reply["ok"], reply
        assert "print: two notes" in reply["warnings"]
    finally:
        app.state.engine.close()


@pytest.mark.parametrize("src", ["s.note('C4', at=bar(2) + 0.5, dur=1)", "x = bar(2) < 3.0", "s.note('C4', at='#drop+1' + beats(1), dur=1)"])
def test_beats_mixed_with_seconds_are_refused_naming_the_form(src):
    with pytest.raises(RostrumError) as e:
        notes(src)
    assert "beats(" in str(e.value)


def test_drum_names_agents_reach_for():
    t = run_source("d = track('d', kit='classic'); d.hit('Hi-Hat', at=0); d.hit('bd', at=1)", "t.py")
    assert [h["drum"] for h in t["tracks"][0]["hits"]] == ["hat", "kick"]
    with pytest.raises(RostrumError, match='write "cymbal"'):
        run_source("d = track('d', kit='classic'); d.hit('crash', at=0)", "t.py")


def test_random_is_the_same_every_run_and_print_comes_back():
    src = "import random\ns.note(random.choice(['C4', 'D4', 'E4', 'F4', 'G4']), at=0, dur=1)\nprint('hi')"
    assert notes(src) == notes(src) and printed() == ["hi"]


def test_timing_slips_are_said_when_the_script_runs_and_never_lock_the_song():
    tie = run_source("s = track('k', builtIn='grandPiano'); s.note('C2', at=10.1, dur={'to': 9.5})", "t.py")
    assert any("not after its start" in w for w in KIND.warn(tie)) and not KIND.check(tie)
    t = run_source("length(10); s = track('k', builtIn='grandPiano'); s.note('C4', at=10.5, dur=1)", "t.py")
    assert any("never heard" in w for w in KIND.warn(t))



def test_a_note_or_section_ends_on_a_marker_or_a_marker_plus_beats():
    t = run_source("tempo(120); length(bar(9)); marker('end', at=bar(8)); s = track('k', builtIn='grandPiano')\n"
                   "s.note('C4', at=bar(2), end='#end')\ns.chord(['C4', 'E4'], at=bar(3), end='#end' - beats(1))\n"
                   "s.note('D4', at=bar(4), dur=until('#end'))\nsection('x', bar(2), '#end' + beats(2))", "t.py")
    assert [n["dur"] for n in t["tracks"][0]["notes"]] == [{"to": "#end"}, {"to": "#end-1beats"}, {"to": "#end"}]
    assert t["sections"][0]["end"] == "#end+2beats"
    with pytest.raises(RostrumError, match="dur="):
        run_source("track('k', builtIn='grandPiano').note('C4', at=0)", "t.py")


def test_marker_beats_follow_the_marker_on_the_tempo_map():
    from rostrum_sound.doc import markers
    doc = {"tempo": 120, "beatsPerBar": 4, "markers": [{"id": "m", "name": "end", "at": 10.0}], "tempos": [], "meters": []}
    assert markers.resolve(doc, "#end+2beats", "t") == 11.0 and markers.resolve(doc, "#end-1beat", "t") == 9.5
    assert markers.renamed("#end+2beats", "end", "out") == "#out+2beats"


def test_a_fixed_end_under_a_moved_marker_is_refused_saying_what_to_write():
    d = Document.new(KIND, folder=None, item="t")
    d.run_script("t.py", run_source("tempo(120); length(20); marker('drop', at=14.2); s = track('k', builtIn='grandPiano')\n"
                                    "s.note('C4', at='#drop+5', dur=until(19.5))", "t.py"), Who.agent("t"))
    d.apply([{"op": "marker.move", "target": ["marker.drop"], "args": {"at": 15.0}}], Who.agent("t"))   # the song's own marker
    said = " ".join(KIND.warn(d.data))
    assert 'marker("end", at=19.5)' in said and 'end="#end"' in said
    with pytest.raises(RostrumError, match='end="#end"'):
        compile(d)
