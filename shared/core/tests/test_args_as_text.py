"""A number or yes/no written as text ("24", "true") is read as one where a tool argument takes it and never text, and
the reply says so; anything else stays refused by the schema check."""
import pytest

from rostrum_core import RostrumError
from rostrum_core.mcp import Reply, Tools

SCHEMA = {"properties": {"samples": {"type": "integer"}, "denoise": {"type": "boolean"}, "scale": {"type": "number"},
                         "seconds": {"anyOf": [{"type": "number"}, {"type": "null"}]}, "name": {"type": "string"},
                         "id": {"type": ["string", "integer"]}}}


def tool():
    tools = Tools()
    return tools.add("render_still", lambda ctx, a: Reply("done", {"got": a}), SCHEMA, "A still.")


def test_numbers_and_yes_no_given_as_text_are_read_and_said():
    notes = []
    got = tool().check({"samples": "24", "denoise": "True", "scale": "0.5", "seconds": "2", "name": "24", "id": "7"}, notes)
    assert got == {"samples": 24, "denoise": True, "scale": 0.5, "seconds": 2, "name": "24", "id": "7"}
    assert notes == ['"samples" came as text ("24"); read as 24.', '"denoise" came as text ("True"); read as true.',
                     '"scale" came as text ("0.5"); read as 0.5.', '"seconds" came as text ("2"); read as 2.']


@pytest.mark.parametrize("args", [{"samples": "24.5"}, {"samples": "lots"}, {"denoise": "yes"}, {"scale": "nan"}])
def test_text_that_is_not_plainly_the_value_is_still_refused(args):
    with pytest.raises(RostrumError):
        tool().check(args, [])


def test_the_reply_carries_the_note():
    from rostrum_core import Who
    from rostrum_core.mcp.server import Runtime
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parents[2] / "mcp" / "demo"))
    import toy_server
    tools = Tools()
    tools.add("render_still", lambda ctx, a: Reply("done", {"got": a}), SCHEMA, "A still.")
    reply = Runtime(toy_server.make_app(), tools).call("render_still", {"samples": "24"}, Who.agent("t"))[0]
    assert reply["ok"] and reply["data"]["got"] == {"samples": 24}
    assert '"samples" came as text ("24"); read as 24.' in reply["warnings"]
