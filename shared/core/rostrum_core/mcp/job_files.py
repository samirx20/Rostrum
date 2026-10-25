"""Jobs seen from other programs: while a job waits or runs, a small file says so, so another server or session can see
it (inspect_job) and stop it (run_stop), which an in-process queue alone can't (an agent once had to end six processes
by hand to stop a stuck render, 2026-10-25).

    <ROSTRUM_DATA or ~/.rostrum>/jobs/<job id>.json    {job_id, label, status, progress, pid: the owner's process, ...}
    <...>/jobs/<job id>.stop                            asked by another program; the owner stops the job within a second

The file goes when the job ends. A file whose owner process is gone (a server ended or killed) is a leftover: read as
"ended with its program", and removed. Nothing here is a lock: no job waits on another program's file.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from ..scratch import running

POLL_S = 1.0                                     # how often a running job's owner looks for a stop asked from outside
_writing = threading.Lock()


def folder() -> Path:
    return Path(os.environ.get("ROSTRUM_DATA") or Path.home() / ".rostrum") / "jobs"


def write(state: dict) -> None:
    """The job's state now, with this process as its owner (written whole, then renamed: a reader never sees half)."""
    d = folder()
    with _writing:                               # one write at a time in this program: the latest state lands last
        try:
            d.mkdir(parents=True, exist_ok=True)
            tmp = d / f"{state['job_id']}.{os.getpid()}.tmp"
            tmp.write_text(json.dumps({**state, "pid": os.getpid(), "updated": time.time()}), encoding="utf-8")
            for _ in range(40):                  # Windows: a reader holding the file for a moment refuses the swap
                try:
                    tmp.replace(d / f"{state['job_id']}.json")
                    break
                except PermissionError:
                    time.sleep(0.025)
        except OSError:
            pass                                 # seeing a job from outside is a help; the job itself never fails for it


def remove(job_id: str) -> None:
    for ext in (".json", ".stop"):
        try:
            (folder() / f"{job_id}{ext}").unlink(missing_ok=True)
        except OSError:
            pass


def read(job_id: str) -> dict | None:
    """Another program's job, or None. Its owner gone: reported ended (status "failed") and its files removed."""
    for _ in range(40):
        try:
            state = json.loads((folder() / f"{job_id}.json").read_text(encoding="utf-8"))
            break
        except PermissionError:                  # Windows: being swapped for a newer state this moment
            time.sleep(0.025)
        except (OSError, ValueError):
            return None
    else:
        return None
    if not running(int(state.get("pid", 0))):
        remove(job_id)
        return {**state, "status": "failed", "reason": f"its program (process {state.get('pid')}) ended before the job did"}
    return state


def others() -> list[dict]:
    """Every job other programs have waiting or running now (leftovers of ended programs are cleared on the way)."""
    try:
        ids = [p.stem for p in folder().glob("*.json")]
    except OSError:
        return []
    out = [read(i) for i in ids]
    return [s for s in out if s and s.get("pid") != os.getpid() and s["status"] in ("queued", "running")]


def ask_stop(job_id: str) -> dict | None:
    """Ask another program's job to stop; its state, or None when no program has that job."""
    state = read(job_id)
    if state is None or state["status"] not in ("queued", "running"):
        return state
    (folder() / f"{job_id}.stop").write_text(str(os.getpid()), encoding="utf-8")
    return state


def stop_asked(job_id: str) -> bool:
    return (folder() / f"{job_id}.stop").exists()


def watch(job, stop) -> threading.Thread:
    """While `job` is not finished, call `stop(job.id)` once if another program asks (a stuck job too: it needs no
    next frame for this)."""
    def loop():
        while not job.finished.wait(POLL_S):
            if stop_asked(job.id):
                stop(job.id)
                return
    t = threading.Thread(target=loop, name=f"rostrum-job-watch-{job.id}", daemon=True)
    t.start()
    return t
