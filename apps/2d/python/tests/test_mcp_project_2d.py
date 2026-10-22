"""What agents rely on: the 2D server, started with no options, opens the person's last project (never Sam's real one in
a test: the settings live in a temp folder), says so plainly when there is none, and run_open_project switches."""
from rostrum_core import Who
from rostrum_core.mcp import Runtime

from rostrum2d import KIND, settings
from rostrum2d.mcp.server import make_app, make_runtime
from rostrum2d.mcp.project_tool import open_project, start_choice

AGENT = Who.agent("tester")


def project(folder, item="main"):
    from rostrum_core import Document
    Document.new(KIND, str(folder), item).save()
    return str(folder)


def start(tmp_path, monkeypatch, recent):
    monkeypatch.setenv("ROSTRUM_DATA", str(tmp_path / "data"))
    settings.write_settings({"recent": recent})
    folder, items = start_choice(None, None)
    app = make_app(folder, items)
    return app, make_runtime(app)


def test_no_options_opens_the_newest_recent_project_and_run_open_project_switches(tmp_path, monkeypatch):
    a, b = project(tmp_path / "a", "intro"), project(tmp_path / "b")
    app, rt = start(tmp_path, monkeypatch, [{"folder": str(tmp_path / "gone"), "item": "main"}, {"folder": a, "item": "intro"}, {"folder": b, "item": "main"}])
    assert app.folder == a and list(app.documents) == ["intro"]            # the missing newest row is skipped
    reply, _ = rt.call("inspect_recent_projects", {}, AGENT)
    assert [r["folder"] for r in reply["data"]["recent"]] == [a, b]
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
