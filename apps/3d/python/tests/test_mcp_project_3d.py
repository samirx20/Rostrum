"""What agents rely on: the 3D server starts with no options on the agent's own scene, never the person's last one
(rostrum_core/agent_start.py), says so in its first reply, and run_open_project switches (the settings live in a temp folder)."""
from rostrum_core import Document, Who, agent_start
from rostrum_core import recent as recent_list
from rostrum_core.mcp import Runtime

from rostrum3d.kind import KIND
from rostrum3d.mcp.project_tool import start_choice
from rostrum3d.mcp.server import app_tools, make_app

AGENT = Who.agent("tester")


def test_no_options_opens_a_scratch_scene_and_run_open_project_switches_to_the_persons(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path))
    person = tmp_path / "person"
    Document.new(KIND, str(person), "scene").save()
    recent_list.remember("3d", KIND.ext, person, "scene", "person")
    start = start_choice(None, None)
    app = make_app(start.folder, start.items)
    agent_start.settle(app, start)
    rt = Runtime(app, app_tools())
    assert "agent-scratch" in app.folder and list(app.documents) == ["scene"]
    reply, _ = rt.call("inspect_project", {}, AGENT)
    assert reply["summary"].startswith("Open: a fresh scratch project made for you") and "not the person's work" in reply["summary"]
    reply, _ = rt.call("run_open_project", {"what": "recent"}, AGENT)
    assert [r["folder"] for r in reply["data"]["recent"]] == [str(person.resolve())]
    reply, _ = rt.call("run_open_project", {"folder": str(person)}, AGENT)
    assert reply["ok"] and app.folder == str(person.resolve()) and list(app.documents) == ["scene"]
    again = start_choice(None, None)                                           # a resumed session reopens what it last opened
    assert again.whose == "resumed" and again.folder == str(person.resolve())
