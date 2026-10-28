"""ROSTRUM2D_TOOLSET=small: four tools on the same engine; the hidden checks stay reachable through look's `check`."""
from rostrum_core import Who
from rostrum2d.mcp.server import make_app, make_runtime

AGENT = Who.agent("tester")


def test_the_small_toolset_shows_four_tools_and_reaches_a_hidden_check(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path))
    monkeypatch.setenv("ROSTRUM_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("ROSTRUM2D_TOOLSET", "small")
    rt = make_runtime(make_app(None))
    assert sorted(t.name for t in rt.tools.all()) == ["export", "look", "read_guide", "run_script"]
    folder = (tmp_path / "film").as_posix()
    assert rt.call("run_script", {"project": folder}, AGENT)[0]["ok"]
    made = rt.call("run_script", {"source": 'comp("main", duration=2)\ntext("title", body="Hi").key("opacity", {0: 0, 1: 1})',
                                  "name": "film.py"}, AGENT)[0]
    assert made["ok"], made
    moves = rt.call("look", {"check": "look_motion", "what": "moves"}, AGENT)[0]
    assert moves["ok"] and "title" in moves["summary"]
    bad = rt.call("look", {"check": "look_motion", "nonsense": 1}, AGENT)[0]
    assert not bad["ok"] and "look_motion" in bad["summary"]
    assert "look" in rt.call("look_frame", {}, AGENT)[0]["summary"]          # an old name says the tool to use
