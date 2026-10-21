"""Agents rely on `inspect_tools` to find tools without their own MCP client: it lists what is registered, by verb."""
import sys
from pathlib import Path

from rostrum_core import Who
from rostrum_core.mcp.server import Runtime

sys.path.insert(0, str(Path(__file__).parents[2] / "mcp" / "demo"))
import toy_server  # noqa: E402


def _call(rt, args):
    return rt.call("inspect_tools", args, Who.agent("test"))[0]


def test_inspect_tools_lists_registered_tools_under_their_verb():
    rt = Runtime(toy_server.make_app(), toy_server.toy_tools)
    reply = _call(rt, {})
    assert reply["ok"]
    listed = {t["name"] for v in reply["data"]["verbs"].values() for t in v}
    assert listed == {t.name for t in rt.tools.all()}
    assert all(t["name"].startswith(v + "_") for v, g in reply["data"]["verbs"].items() for t in g)
    one = _call(rt, {"name": "edit_document"})["data"]["tool"]
    assert "ops" in [a["name"] for a in one["arguments"]]
    bad = _call(rt, {"verb": "nope"})
    assert bad["error"]["code"] == "NOT_FOUND" and "inspect" in bad["error"]["accepted"]
