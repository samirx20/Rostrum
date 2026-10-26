"""look_frame `times`: one contact sheet of exactly those moments, and a bad list is refused whole, loudly."""
import sys

import pytest
from rostrum_core import Who
from rostrum_core.mcp import Runtime

from rostrum2d import settings
from rostrum2d.mcp import app_tools, make_app

AGENT = Who.agent("tester")
needs_engine = pytest.mark.skipif(settings.engine_missing_reason() is not None or sys.platform != "win32",
                                  reason=settings.engine_missing_reason() or "the engine's pixels are Windows only")


def start(tmp_path):
    rt = Runtime(make_app(str(tmp_path), ["demo"]), app_tools())
    rt.call("run_script", {"source": 'comp("main", width=640, height=360, fps=30, duration=2)\nshape("a", shape="rect", x=100, y=100, w=50, h=50)', "name": "s.py"}, AGENT)
    return rt


def test_a_bad_times_list_is_refused_naming_the_problem(tmp_path):
    rt = start(tmp_path)
    for args, words in (({"times": [0.5, 9]}, "9 s"), ({"times": [0.5, 1], "time": 1}, '"times" and "time"')):
        reply, _ = rt.call("look_frame", args, AGENT)
        assert not reply["ok"] and words in reply["summary"]


@needs_engine
def test_times_gives_one_sheet_of_those_moments(tmp_path):
    reply, _ = start(tmp_path).call("look_frame", {"times": [1.0, 0.2, 0.5]}, AGENT)
    assert reply["ok"] and reply["data"]["result"]["times"] == [0.2, 0.5, 1.0] and len(reply["files"]) == 1
