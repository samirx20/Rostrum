"""What agents rely on: the 2D server, started with no options, opens the person's last project (never Sam's real one in
a test: the settings live in a temp folder), says so plainly when there is none, and run_open_project switches."""
import json

from rostrum_core import Who
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
    folder, items = start_choice(None, None)
    app = make_app(folder, items)
    return app, make_runtime(app)


def test_no_options_opens_the_newest_recent_project_and_run_open_project_switches(tmp_path, monkeypatch):
    a, b = project(tmp_path / "a", "intro"), project(tmp_path / "b")
    app, rt = start(tmp_path, monkeypatch, [{"folder": str(tmp_path / "gone"), "item": "main"}, {"folder": a, "item": "intro"}, {"folder": b, "item": "main"}])
    assert app.folder == a and list(app.documents) == ["intro"]            # the missing newest row is skipped
    reply, _ = rt.call("run_open_project", {"what": "recent"}, AGENT)
    assert [r["folder"] for r in reply["data"]["recent"]] == [a, b]
    reply, _ = rt.call("inspect_recent_projects", {}, AGENT)             # an old name never silently works: it names the new call
    assert not reply["ok"] and reply["error"]["code"] == "UNKNOWN_TOOL" and 'run_open_project with what: "recent"' in reply["summary"]
    reply, _ = rt.call("run_open_project", {"folder": b}, AGENT)
    assert reply["ok"], reply
    reply, _ = rt.call("inspect_project", {}, AGENT)
    assert reply["data"]["folder"] == b and [d["item"] for d in reply["data"]["open"]] == ["main"]
    reply, _ = rt.call("run_open_project", {"folder": a, "item": "nope"}, AGENT)
    assert not reply["ok"] and reply["error"]["code"] == "NOT_FOUND" and reply["error"]["accepted"] == ["intro"]


def test_with_no_recent_project_nothing_is_open_and_nothing_is_created(tmp_path, monkeypatch):
    app, rt = start(tmp_path, monkeypatch, [])
    assert app.documents == {} and app.folder is None
    reply, _ = rt.call("inspect_project", {}, AGENT)
    assert reply["ok"] and reply["summary"].startswith("No project is open. Open one in Rostrum2D, or call run_open_project")
    assert not any(tmp_path.glob("*/docs"))
