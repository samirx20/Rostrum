"""What agents rely on: the Sound server, started with no options, opens the agent's own song, never the person's last one
(rostrum_core/agent_start.py; the settings live in a temp folder), its first reply says which, and run_open_project
switches (one engine stays)."""
import json

from rostrum_core import Document, Who, agent_start

from rostrum_sound import KIND
from rostrum_sound.mcp.app import make_app
from rostrum_sound.mcp.server import make_runtime
from rostrum_sound.mcp.tools_project import start_choice

AGENT = Who.agent("tester")


def song(folder, item="song"):
    Document.new(KIND, folder=str(folder), item=item).save()
    return str(folder)


def start(tmp_path, monkeypatch, recent):
    # A scripted run's Open recent lives in its scratch home (rostrum_core/userhome.py), never the person's: this test's is tmp_path.
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path))
    monkeypatch.setenv("ROSTRUM_SETTINGS_DIR", str(tmp_path / "settings"))
    (tmp_path / "engine.exe").write_bytes(b"")                      # the engine starts on first use; these tests never use it
    monkeypatch.setenv("ROSTRUM_SOUND_ENGINE", str(tmp_path / "engine.exe"))
    (tmp_path / "settings").mkdir()
    (tmp_path / "settings" / "sound-recent.json").write_text(json.dumps(recent), encoding="utf-8")
    start = start_choice(None, None)
    app = make_app(start.folder, start.items)
    agent_start.settle(app, start)
    return app, make_runtime(app)


def test_no_options_never_opens_the_persons_last_song_and_run_open_project_switches(tmp_path, monkeypatch):
    a, b = song(tmp_path / "a", "mix"), song(tmp_path / "b")
    app, rt = start(tmp_path, monkeypatch, [{"folder": a, "item": "mix", "name": "a"}, {"folder": b, "item": "song", "name": "b"}])
    try:
        engine = app.state.engine
        assert app.folder not in (a, b) and "agent-scratch" in app.folder and list(app.documents) == ["song"]
        reply, _ = rt.call("inspect_project", {}, AGENT)                      # the first reply says what is open and whose
        assert reply["summary"].startswith("Open: a fresh scratch project made for you") and 'song "song"' in reply["summary"]
        reply, _ = rt.call("run_open_project", {"folder": b}, AGENT)
        assert reply["ok"], reply
        reply, _ = rt.call("inspect_project", {}, AGENT)
        assert reply["data"]["folder"] == b and [d["item"] for d in reply["data"]["open"]] == ["song"]
        assert app.state.folder.name == "b" and app.state.engine is engine
        reply, _ = rt.call("run_open_project", {"folder": b, "item": "verse"}, AGENT)    # a new name starts a new song, naming the others
        assert reply["ok"] and reply["data"]["others"] == ["song"] and list(app.documents) == ["verse"]
    finally:
        app.state.engine.close()
