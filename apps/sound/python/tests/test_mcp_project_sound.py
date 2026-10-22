"""What agents rely on: the Sound server, started with no options, opens the person's last song (the settings live in a
temp folder, never Sam's), says so plainly when there is none, and run_open_project switches (one engine stays)."""
import json

from rostrum_core import Document, Who

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
    folder, items = start_choice(None, None)
    app = make_app(folder, items)
    return app, make_runtime(app)


def test_no_options_opens_the_newest_recent_song_and_run_open_project_switches(tmp_path, monkeypatch):
    a, b = song(tmp_path / "a", "mix"), song(tmp_path / "b")
    app, rt = start(tmp_path, monkeypatch, [{"folder": a, "item": "mix", "name": "a"}, {"folder": b, "item": "song", "name": "b"}])
    try:
        engine = app.state.engine
        assert app.folder == a and list(app.documents) == ["mix"]
        reply, _ = rt.call("run_open_project", {"folder": b}, AGENT)
        assert reply["ok"], reply
        reply, _ = rt.call("inspect_project", {}, AGENT)
        assert reply["data"]["folder"] == b and [d["item"] for d in reply["data"]["open"]] == ["song"]
        assert app.state.folder.name == "b" and app.state.engine is engine
        reply, _ = rt.call("run_open_project", {"folder": b, "item": "nope"}, AGENT)
        assert not reply["ok"] and reply["error"]["code"] == "NOT_FOUND" and reply["error"]["accepted"] == ["song"]
    finally:
        app.state.engine.close()


def test_with_no_recent_song_nothing_is_open_and_nothing_is_created(tmp_path, monkeypatch):
    app, rt = start(tmp_path, monkeypatch, [])
    try:
        assert app.documents == {} and app.folder is None
        reply, _ = rt.call("inspect_project", {}, AGENT)
        assert reply["ok"] and reply["summary"].startswith("No project is open. Open one in RostrumSound, or call run_open_project")
    finally:
        app.state.engine.close()
