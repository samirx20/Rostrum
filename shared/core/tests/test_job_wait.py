"""Agents rely on `wait` on look_/render_ tools: the finished file comes back in the same reply, a job still running
past the wait is said plainly with its id (never a success), and a failed job is an error."""
import threading
import time

from rostrum_core import Who
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_core.mcp.server import Runtime


def _rt(work):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parents[2] / "mcp" / "demo"))
    import toy_server
    tools = Tools()
    tools.add("render_thing", lambda ctx, a: Reply("queued", ctx.jobs.submit("thing", work).state()), {}, "Renders a thing.")
    rt = Runtime(toy_server.make_app(), tools)
    rt.jobs._shared = False                       # no job files outside the test
    return rt


def test_wait_answers_with_the_finished_file():
    rt = _rt(lambda job: (time.sleep(0.2), Reply("made", {"n": 1}, ["C:/out/thing.mp4"]))[1])
    assert "wait" in {a for a in rt.tools.get("render_thing").schema["properties"]}
    reply = rt.call("render_thing", {"wait": True}, Who.agent("t"))[0]
    assert reply["ok"] and reply["data"]["status"] == "done" and reply["files"] == ["C:/out/thing.mp4"]
    plain = rt.call("render_thing", {}, Who.agent("t"))[0]          # no wait: the job id at once
    assert plain["data"]["status"] in ("queued", "running")


def test_wait_past_its_time_says_still_running_and_a_failure_is_an_error():
    gate = threading.Event()
    rt = _rt(lambda job: (gate.wait(5), Reply("made"))[1])
    reply = rt.call("render_thing", {"wait": 0.3}, Who.agent("t"))[0]
    assert reply["ok"] and reply["data"]["status"] in ("queued", "running") and "Still running" in reply["summary"]
    gate.set()

    def boom(job):
        raise RostrumError(codes.BAD_ARGUMENT, "render", "thing", "broke")
    failed = _rt(boom).call("render_thing", {"wait": 5}, Who.agent("t"))[0]
    assert not failed["ok"] and failed["error"]["code"] == "JOB_FAILED"
    bad = _rt(boom).call("render_thing", {"wait": 9999}, Who.agent("t"))[0]
    assert not bad["ok"] and "wait" in bad["summary"]
