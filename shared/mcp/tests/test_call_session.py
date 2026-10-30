"""Agents without an MCP client rely on call.py's session: a later command reuses the running server (a job started
by one command is still there for the next), the server records the calls as `agent:<name>`, a dead session is said
plainly and replaced, and `stop` ends it."""
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CALL = ROOT / "shared" / "mcp" / "call.py"
SERVER = textwrap.dedent('''
    import sys, time
    sys.path.insert(0, sys.argv[1])
    import toy_server
    from rostrum_core.mcp import Reply, Tools, run_stdio
    tools = Tools()
    tools.add("render_slow", lambda ctx, a: Reply("queued", ctx.jobs.submit("slow", lambda job: (time.sleep(1.5), Reply("made", {}, ["C:/out/slow.mp4"]))[1]).state()), {}, "A slow render.")
    tools.add("render_long", lambda ctx, a: Reply("queued", ctx.jobs.submit("long", lambda job: (time.sleep(5), Reply("made", {"frames": 2400}, ["C:/out/long.mp4"]))[1]).state()), {}, "A long export.")
    run_stdio(toy_server.make_app(), toy_server.toy_tools.merged_with(tools))
''')


@pytest.fixture
def call(tmp_path):
    server = tmp_path / "server.py"
    server.write_text(SERVER, encoding="utf-8")
    env = {**os.environ, "ROSTRUM_DATA": str(tmp_path / "data"),
           "PYTHONPATH": os.pathsep.join(str(ROOT / p) for p in ("shared/core", "shared/mcp"))}
    head = [sys.executable, str(CALL), "--name", "agent-sess", "--", sys.executable, str(server), str(ROOT / "shared" / "mcp" / "demo")]

    def run(*steps):
        out = subprocess.run([*head, *steps], capture_output=True, text=True, encoding="utf-8", env=env, cwd=tmp_path, timeout=90)
        return out.returncode, out.stdout + out.stderr
    yield run, tmp_path / "data" / "call-sessions"
    run("::", "stop")


def _record(folder: Path) -> dict:
    return json.loads(next(folder.glob("*.json")).read_text(encoding="utf-8"))


def test_a_job_started_in_one_command_is_there_in_the_next(call):
    run, folder = call
    rc, out = run("::", "render_slow")
    assert rc == 0, out
    job = re.search(r'"job_id": "(job_\w+)"', out).group(1)
    pid = _record(folder)["pid"]
    rc, out = run("::", "inspect_job", json.dumps({"job_id": job, "wait_s": 10}), "::", "inspect_history")
    assert rc == 0 and '"status": "done"' in out and "slow.mp4" in out, out
    assert _record(folder)["pid"] == pid                         # the same session, not a new server
    rc, out = run("::", "render_slow", '{"wait": true}')         # waits in the call: the finished file in this reply
    assert rc == 0 and '"status": "done"' in out and "slow.mp4" in out, out
    rc, out = run("::", "run_script", json.dumps({"source": 'rect("a", x=5)', "name": "s.py"}), "::", "inspect_history")
    assert '"name": "agent-sess"' in out and '"kind": "agent"' in out, out


def test_a_dead_session_is_said_and_replaced_and_stop_ends_it(call):
    run, folder = call
    assert run("::", "look_summary")[0] == 0
    old = _record(folder)["pid"]
    subprocess.run(["taskkill", "/F", "/PID", str(old)] if os.name == "nt" else ["kill", "-9", str(old)], capture_output=True)
    rc, out = run("::", "look_summary")
    assert rc == 0 and "is gone" in out and "jobs started in the old session are gone" in out, out
    assert _record(folder)["pid"] != old
    rc, out = run("::", "nope_tool", "::", "look_summary")       # stop at the first failure, exit 1
    assert rc == 1 and "NOT run: 2. look_summary" in out, out
    rc, out = run("::", "stop")
    assert rc == 0 and "ended" in out and not list(folder.glob("*.json")), out


def test_a_job_outlives_its_session_and_its_result_is_read_from_the_next(call):
    """Showreel, 2026-10-28: an export died at frame 562 of 2400 when its session ended. Ending a session with a job
    running keeps its server until the job ends; the next session reads the job's result."""
    run, folder = call
    rc, out = run("::", "render_long", '{"wait": false}')     # in the background: the session ends while it runs
    assert rc == 0, out
    job = re.search(r'"job_id": "(job_\w+)"', out).group(1)
    old = _record(folder)["pid"]
    rc, out = run("::", "stop")
    assert rc == 0 and "1 running job(s)" in out and not list(folder.glob("*.json")), out
    rc, out = run("::", "inspect_job", json.dumps({"job_id": job, "wait_s": 20}))   # a fresh session (and server)
    assert _record(folder)["pid"] != old
    assert rc == 0 and '"status": "done"' in out and "long.mp4" in out and '"frames": 2400' in out, out
