"""What agents rely on: the 2D server, started with no options, opens the agent's own project, never the person's last one
(rostrum_core/agent_start.py; the settings live in a temp folder in a test), its first reply says which, and
run_open_project lists the person's projects and switches."""
import json

from rostrum_core import Who, agent_start
from rostrum_core import recent as recent_list
from rostrum_core.mcp import Runtime

from rostrum2d import KIND
from rostrum2d.mcp.server import make_app, make_runtime
from rostrum2d.mcp.project_tool import open_project, start_choice

AGENT = Who.agent("tester")


def project(folder, item="main"):
    from rostrum_core import Document
    Document.new(KIND, str(folder), item).save()
    return str(folder)


def start(tmp_path, monkeypatch, recent):
    # A scripted run's Open recent lives in its scratch home (rostrum_core/userhome.py), never the person's: this test's is tmp_path.
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path))
    monkeypatch.setenv("ROSTRUM_DATA", str(tmp_path / "data"))
    recent_file = recent_list.file("2d")                                # the one Open recent list (rostrum_core/recent.py)
    recent_file.parent.mkdir(parents=True, exist_ok=True)
    recent_file.write_text(json.dumps(recent), encoding="utf-8")
    start = start_choice(None, None)
    app = make_app(start.folder, start.items)
    agent_start.settle(app, start)
    return app, make_runtime(app)


def test_no_options_never_opens_the_persons_last_project_and_run_open_project_switches(tmp_path, monkeypatch):
    a, b = project(tmp_path / "a", "intro"), project(tmp_path / "b")
    app, rt = start(tmp_path, monkeypatch, [{"folder": str(tmp_path / "gone"), "item": "main"}, {"folder": a, "item": "intro"}, {"folder": b, "item": "main"}])
    assert app.folder not in (a, b) and "agent-scratch" in app.folder and list(app.documents) == ["main"]
    reply, _ = rt.call("inspect_project", {}, AGENT)                          # the first reply says what is open and whose
    assert reply["summary"].startswith("Open: a fresh scratch project made for you") and "not the person's work" in reply["summary"]
    reply, _ = rt.call("run_open_project", {"what": "recent"}, AGENT)        # the missing newest row is skipped
    assert [r["folder"] for r in reply["data"]["recent"]] == [a, b]
    reply, _ = rt.call("inspect_recent_projects", {}, AGENT)             # an old name never silently works: it names the new call
    assert not reply["ok"] and reply["error"]["code"] == "UNKNOWN_TOOL" and 'run_open_project with what: "recent"' in reply["summary"]
    reply, _ = rt.call("run_open_project", {"folder": b}, AGENT)
    assert reply["ok"], reply
    reply, _ = rt.call("inspect_project", {}, AGENT)
    assert reply["data"]["folder"] == b and [d["item"] for d in reply["data"]["open"]] == ["main"]
    reply, _ = rt.call("run_open_project", {"folder": a, "item": "teaser"}, AGENT)    # a new name starts a new document,
    assert reply["ok"] and "intro" in reply["summary"] and list(app.documents) == ["teaser"]   # saying what else is there


def test_run_open_project_makes_a_new_folder_and_a_refused_call_makes_nothing(tmp_path, monkeypatch):
    app, rt = start(tmp_path, monkeypatch, [])
    reply, _ = rt.call("run_open_project", {"folder": str(tmp_path / "x" / "bad"), "item": "a b"}, AGENT)
    assert not reply["ok"] and not (tmp_path / "x").exists()
    reply, _ = rt.call("run_open_project", {"folder": str(tmp_path / "new" / "piece")}, AGENT)
    assert reply["ok"] and (tmp_path / "new" / "piece" / "docs" / "main.mtn").is_file()


def test_a_resumed_session_gets_its_project_back(tmp_path, monkeypatch):
    # The fair benchmark's refine turns all began with "no document is open": the resumed session's new server had forgotten
    # the project the agent opened with run_open_project (it never enters the person's Open recent list).
    person = project(tmp_path / "person")
    app, rt = start(tmp_path, monkeypatch, [{"folder": person, "item": "main"}])
    assert app.folder != person
    reply, _ = rt.call("run_open_project", {"folder": str(tmp_path / "agent" / "piece")}, AGENT)
    assert reply["ok"], reply
    app, rt = start(tmp_path, monkeypatch, [{"folder": person, "item": "main"}])   # the next server, same working folder
    assert app.folder == str((tmp_path / "agent" / "piece").resolve()) and list(app.documents) == ["main"]
    reply, _ = rt.call("inspect_project", {}, AGENT)
    assert "your project from earlier in this session" in reply["summary"]
    empty = make_runtime(make_app(None, []))
    reply, _ = empty.call("look_frame", {}, AGENT)
    assert not reply["ok"] and "run_open_project" in reply["summary"]      # with nothing open, the reply says how to fix it
