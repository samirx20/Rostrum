"""A render answers once, when it is finished: render_* waits for its job by default (as long as the calling program lets
a call run), the finished file comes back in the same reply, a job still running past the wait is said plainly with
how far and its id (never a success), the next inspect_job waits again, and a failed job is an error."""
import threading
import time

from rostrum_core import Who
from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools, job_wait
from rostrum_core.mcp.server import Runtime

CLAUDE = Who.agent("claude-code")


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
    plain = rt.call("render_thing", {"wait": False}, Who.agent("t"))[0]   # wait false: the job id at once
    assert plain["data"]["status"] in ("queued", "running")


def test_wait_past_its_time_says_still_running_and_a_failure_is_an_error():
    gate = threading.Event()
    rt = _rt(lambda job: (gate.wait(5), Reply("made"))[1])
    reply = rt.call("render_thing", {"wait": 0.3}, Who.agent("t"))[0]
    assert reply["ok"] and reply["data"]["status"] in ("queued", "running") and "Still rendering" in reply["summary"]
    gate.set()

    def boom(job):
        raise RostrumError(codes.BAD_ARGUMENT, "render", "thing", "broke")
    failed = _rt(boom).call("render_thing", {"wait": 5}, Who.agent("t"))[0]
    assert not failed["ok"] and failed["error"]["code"] == "JOB_FAILED"
    bad = _rt(boom).call("render_thing", {"wait": 9999}, Who.agent("t"))[0]
    assert not bad["ok"] and "wait" in bad["summary"]


def test_a_render_waits_by_default_and_answers_once_finished():
    """One call, no `wait`: the finished file (a fake slow job of ~1 s, well inside Claude Code's budget)."""
    def slow(job):
        for i in range(5):
            time.sleep(0.2)
            job.progress(i + 1, 5, f"frame {i + 1} of 5")
        return Reply("made", {"n": 1}, ["C:/out/thing.mp4"])
    rt = _rt(slow)
    reply = rt.call("render_thing", {}, CLAUDE)[0]
    assert reply["ok"] and reply["data"]["status"] == "done" and reply["files"] == ["C:/out/thing.mp4"]


def test_a_job_longer_than_the_limit_answers_before_it_and_the_next_call_finishes_it(monkeypatch):
    """The program's limit (here 0.6 s): the render answers just before it with how far it is; inspect_job (no
    wait_s) waits again and answers with the finished file. No tight polling: two calls in all."""
    monkeypatch.setenv(job_wait.ENV, "0.6")
    started = threading.Event()

    def slow(job):
        started.set()
        for i in range(10):
            time.sleep(0.1)
            job.progress(i + 1, 10, f"frame {i + 1} of 10")
        return Reply("made", {"n": 1}, ["C:/out/thing.mp4"])
    rt = _rt(slow)
    t0 = time.monotonic()
    first = rt.call("render_thing", {}, CLAUDE)[0]
    took = time.monotonic() - t0
    assert first["ok"] and first["data"]["status"] == "running", first["summary"]
    assert 0.5 <= took < 0.95, took                      # waited its budget, answered before the job's ~1 s
    assert "Still rendering, " in first["summary"] and " %" in first["summary"] and "inspect_job" in first["summary"]
    job_id = first["data"]["job_id"]
    second = rt.call("inspect_job", {"job_id": job_id}, CLAUDE)[0]
    assert second["ok"] and second["data"]["status"] == "done" and second["files"] == ["C:/out/thing.mp4"], second["summary"]
    now = rt.call("inspect_job", {"job_id": job_id, "wait_s": 0}, CLAUDE)[0]     # wait_s 0: as it is, at once
    assert now["data"]["status"] == "done"


def test_inspect_job_wait_s_0_answers_at_once():
    gate = threading.Event()
    rt = _rt(lambda job: (gate.wait(5), Reply("made"))[1])
    job_id = rt.call("render_thing", {"wait": False}, CLAUDE)[0]["data"]["job_id"]
    t0 = time.monotonic()
    now = rt.call("inspect_job", {"job_id": job_id, "wait_s": 0}, CLAUDE)[0]
    assert now["data"]["status"] in ("queued", "running") and time.monotonic() - t0 < 0.5
    gate.set()


def test_the_budget_stays_under_each_programs_limit(monkeypatch):
    monkeypatch.delenv(job_wait.ENV, raising=False)
    assert job_wait.budget(Who.agent("claude-code")) == 1500 < 1800       # Claude Code: ends a stdio call silent for 30 min
    assert job_wait.budget(Who.agent("cli-agent")) == 1500                 # shared/mcp/call.py: no limit
    assert job_wait.budget(Who.agent("codex")) == 50 < 60                  # anyone else: under the ~60 s many clients allow
    assert job_wait.budget(None) == 50
    monkeypatch.setenv(job_wait.ENV, "120")
    assert job_wait.budget(Who.agent("codex")) == 120


def test_a_look_still_waits_only_when_asked():
    gate = threading.Event()
    rt = _rt(lambda job: Reply("made"))
    rt.tools.add("look_thing", lambda ctx, a: Reply("queued", ctx.jobs.submit("look", lambda j: (gate.wait(5), Reply("seen"))[1]).state()), {}, "Looks.")
    reply = rt.call("look_thing", {}, CLAUDE)[0]
    assert reply["data"]["status"] in ("queued", "running")
    gate.set()


def test_the_finished_reply_passes_the_apps_hook():
    rt = _rt(lambda job: Reply("made", {"n": 1}))
    rt.waited.append(lambda ctx, args, reply: (setattr(reply, "summary", reply.summary + " [clock]"), reply)[1])
    reply = rt.call("render_thing", {}, CLAUDE)[0]
    assert reply["data"]["status"] == "done" and reply["summary"].endswith("[clock]")
