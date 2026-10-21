"""What agents rely on from the MCP server: a failed edit says where and changes nothing; a script re-run keeps a person's work."""
import json
import sys
from pathlib import Path

import anyio
from mcp import Client
from mcp_types import Implementation

from rostrum_core import Who
from rostrum_core.mcp import build_server

sys.path.insert(0, str(Path(__file__).parents[2] / "mcp" / "demo"))
import toy_server  # noqa: E402


async def _call(app, calls):
    """Run (tool, args) calls through the real SDK, in memory. Returns [(is_error, reply dict)]."""
    async with Client(build_server(app, toy_server.toy_tools), client_info=Implementation(name="test-agent", version="1")) as c:
        out = []
        for name, args in calls:
            r = await c.call_tool(name, args)
            out.append((r.is_error, json.loads(r.content[0].text)))
        return out


def test_failed_op_names_itself_and_nothing_is_applied():
    app = toy_server.make_app()
    doc = app.documents["toy_1"]
    ops = [{"op": "layer.move", "target": ["card"], "args": {"x": 99}}, {"op": "layer.move", "target": ["nope"], "args": {"x": 1}}]
    [(is_error, reply)] = anyio.run(_call, app, [("edit_document", {"ops": ops})])
    assert is_error and reply["ok"] is False
    assert reply["error"]["code"] == "NOT_FOUND" and reply["error"]["where"].startswith("edit_document › op 2 of 2 (layer.move)")
    assert reply["summary"].startswith("Error: edit_document › op 2 of 2")
    assert doc.seq == 0 and doc.item("card")["x"] == 0           # op 1 was not applied either


def test_script_rerun_keeps_a_persons_change_and_reports_it():
    app = toy_server.make_app()
    doc = app.documents["toy_1"]
    run = ("run_script", {"source": 'rect("logo", x=400)', "name": "intro.py"})
    anyio.run(_call, app, [run])
    doc.apply({"op": "layer.move", "target": ["logo"], "args": {"x": 777}}, Who.person("sam"))     # a person drags it
    [(is_error, reply)] = anyio.run(_call, app, [("run_script", {"source": 'rect("logo", x=500)', "name": "intro.py"})])
    assert not is_error and doc.item("logo")["x"] == 777
    assert [h["key"] for h in reply["data"]["held"]] == ["logo.x"] and "logo.x" in reply["warnings"][0]
    assert doc.who_changed("logo", "x").who == Who.person("sam")
