"""A job another program runs can be seen and stopped from here, even when it is stuck (no progress step), and a job
file left by a program that ended never looks alive (job_files.py). p1, 2026-10-25: a stuck render could only be ended
by hand, process by process."""
import json
import os
import subprocess
import sys
import time

from rostrum_core.mcp import job_files
from rostrum_core.mcp.jobs import InProcessJobs

OWNER = r"""
import sys, threading
from rostrum_core.mcp.jobs import InProcessJobs
jobs = InProcessJobs()
def stuck(job):                       # never steps: only its stop hook (as a render's engine end) lets it out
    ended = threading.Event()
    job.on_cancel(ended.set)
    ended.wait(60)
    raise RuntimeError("its engine was ended")
job = jobs.submit("render_video stuck", stuck)
print(job.id, flush=True)
job.finished.wait(60)
print(job.status, flush=True)
"""


def test_another_programs_stuck_job_is_seen_and_stopped(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_DATA", str(tmp_path))
    owner = subprocess.Popen([sys.executable, "-c", OWNER], stdout=subprocess.PIPE, text=True, env=dict(os.environ))
    try:
        job_id = owner.stdout.readline().strip()
        here = InProcessJobs()
        seen = here.wait(job_id, 3)
        assert seen.owner not in (None, os.getpid()) and seen.status == "running"   # (a venv python runs as a child: its own pid)
        assert [j.id for j in here.listing()] == [job_id]
        here.cancel(job_id)
        assert owner.stdout.readline().strip() == "cancelled"
        owner.wait(10)
        assert job_files.read(job_id)["status"] == "cancelled"   # its file keeps its end (a later session reads it)
    finally:
        if owner.poll() is None:
            owner.kill()


def test_a_job_file_left_by_an_ended_program_reads_as_ended(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_DATA", str(tmp_path))
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    (tmp_path / "jobs").mkdir()
    (tmp_path / "jobs" / "job_dead01.json").write_text(json.dumps({"job_id": "job_dead01", "label": "x", "status": "running",
                                                                   "pid": gone.pid, "updated": time.time()}))
    assert job_files.read("job_dead01")["status"] == "failed"
    assert not (tmp_path / "jobs" / "job_dead01.json").exists()
