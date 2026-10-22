"""The scene's soundtrack (UX_SPEC 3.28): agents read what plays (inspect_soundtrack), a wrong pick is a loud error
naming the Sound items, and the field never reaches the 2D engine (it refuses fields it doesn't know)."""
from rostrum_core import Document, Who, markers
from rostrum_core.mcp import Runtime
from rostrum_core.storage import save

from rostrum2d.mcp import app_tools, make_app
from rostrum2d.scene import describe

AGENT = Who.agent("tester")


def project(tmp_path):
    from rostrum_sound import KIND as SOUND, run_source
    from rostrum_sound.doc import markers as sound_markers
    (tmp_path / "docs").mkdir()
    markers.edit(tmp_path, [{"op": "marker.add", "args": {"name": "drop", "at": 2.0}}], AGENT)
    with sound_markers.project(tmp_path):
        song = Document.new(SOUND, tmp_path, "song")
        song.run_script("s.py", run_source('tempo(120); length(bar(3))\nd = track("d", kit="synth")\n'
                                           'd.hit("kick", at="#drop")', "s.py"), AGENT)
        save(song)
    app = make_app(str(tmp_path), ["film"])
    rt = Runtime(app, app_tools())
    rt.call("run_script", {"source": 'comp("main", width=320, height=180, fps=30, duration=4)', "name": "f.py"}, AGENT)
    return app, rt


def test_agents_read_what_plays_and_a_wrong_pick_is_loud(tmp_path):
    app, rt = project(tmp_path)
    reply, _ = rt.call("inspect_soundtrack", {}, AGENT)
    f = reply["data"]["soundtrack"]
    assert (f["item"], f["seconds"], f["bpm"], f["bars"]) == ("song", 4.0, 120.0, [0.0, 2.0, 4.0])
    assert f["markers"] == [{"name": "drop", "at": 2.0}]
    doc = app.documents["film"]
    doc.apply([{"op": "comp.set", "target": ["main"], "args": {"soundtrack": "nope"}}], AGENT)
    reply, _ = rt.call("inspect_soundtrack", {}, AGENT)
    assert not reply["ok"] and "not a RostrumSound item" in str(reply) and "song" in str(reply)
    assert "soundtrack" not in describe(doc.data, "main", {}, None, (0, 4))["comp"]["props"]
