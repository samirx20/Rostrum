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


def test_combined_tool_checks_the_chosen_part_and_old_names_say_the_new_call():
    from rostrum_core.mcp import Reply, Tools
    from rostrum_core.mcp.combine import combine
    tools = Tools()
    tools.add("look_one", lambda ctx, a: Reply("one", {"got": a}), {"properties": {"time": {"type": "number"}}}, "One picture.")
    tools.add("look_many", lambda ctx, a: Reply("many", {"got": a}), {"required": ["count"], "properties": {"count": {"type": "integer"}}}, "Many.")
    combine(tools, "look_one", "Pictures: one (default) or many.", {"one": "look_one", "many": "look_many"}, default="one")
    rt, who = Runtime(toy_server.make_app(), tools), Who.agent("test")
    assert rt.call("look_one", {"time": 2}, who)[0]["data"]["got"] == {"time": 2}
    assert rt.call("look_one", {"what": "many", "count": 3}, who)[0]["data"]["got"] == {"count": 3}
    wrong = rt.call("look_one", {"what": "many", "time": 2}, who)[0]          # an argument of another choice: loud
    assert not wrong["ok"] and 'with what "many"' in wrong["summary"]
    assert not rt.call("look_one", {"what": "many"}, who)[0]["ok"]            # the part's own required argument
    old = rt.call("look_many", {"count": 3}, who)[0]
    assert old["error"]["code"] == "UNKNOWN_TOOL" and 'Use look_one with what: "many"' in old["summary"]


def test_core_tools_come_first_in_the_list_and_in_inspect_tools():
    from rostrum_core.mcp import Reply, Tools
    tools = Tools()
    for n in ("look_one", "run_two", "edit_three"):
        tools.add(n, lambda ctx, a: Reply("ok"), {}, f"{n} does its job.")
    tools.core = ["edit_three", "look_one"]
    rt = Runtime(toy_server.make_app(), tools)
    assert [t.name for t in rt.tools.all()][:2] == ["edit_three", "look_one"]
    reply = _call(rt, {})
    assert reply["data"]["core"] == ["edit_three", "look_one"]
    assert reply["summary"].split("\n")[1].startswith("Start with: edit_three (edit_three does its job.); look_one")
    assert "core" not in _call(rt, {"verb": "look"})["data"]
