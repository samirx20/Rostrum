"""Jobs for long work: a small in-process stand-in for the project service's one queue (CONVENTIONS § 7).

The real queue (shared/project-service/CONTRACT.md) swaps in behind `Jobs`: same four calls, same job fields.
A job's function runs in a worker thread and must NOT touch the document: it returns a Reply, and the
document changes only through an operation afterwards (OPERATIONS.md § 1).
"""
from __future__ import annotations

import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Protocol

from ..errors import RostrumError, codes
from .reply import Reply

MAX_WAIT_S = 25


class Job:
    def __init__(self, label: str, key: str | None):
        self.id = "job_" + uuid.uuid4().hex[:4]
        self.label, self.key = label, key
        self.status = "queued"                  # queued | running | done | failed | cancelled
        self.done = self.total = None
        self.note = ""
        self.result: Reply | None = None
        self.reason = ""
        self.cancel_requested = threading.Event()
        self.finished = threading.Event()

    def progress(self, done=None, total=None, note: str = ""):
        """Called by the job's function. Also the place a long job notices a stop request."""
        self.done, self.total, self.note = done, total, note
        if self.cancel_requested.is_set():
            raise _Cancelled()

    def state(self) -> dict:
        out = {"job_id": self.id, "label": self.label, "status": self.status, "note": self.note}
        if self.total:
            out["progress"] = {"done": self.done, "total": self.total}
        return out


class _Cancelled(Exception):
    pass


class Jobs(Protocol):
    def submit(self, label: str, fn: Callable[[Job], Reply], key: str | None = None) -> Job: ...
    def get(self, job_id: str) -> Job: ...
    def wait(self, job_id: str, wait_s: float) -> Job: ...
    def cancel(self, job_id: str) -> Job: ...


class InProcessJobs:
    def __init__(self, workers: int = 1, log=None):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="rostrum-job")   # one heavy job at a time
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._log = log                                   # callable(text) -> log path, for unexpected failures

    def submit(self, label, fn, key=None) -> Job:
        with self._lock:
            for j in self._jobs.values():                 # the same work again joins the running job
                if key and j.key == key and j.status in ("queued", "running"):
                    return j
            job = Job(label, key)
            self._jobs[job.id] = job
        self._pool.submit(self._run, job, fn)
        return job

    def _run(self, job: Job, fn):
        if job.cancel_requested.is_set():
            job.status = "cancelled"
            job.finished.set()
            return
        job.status = "running"
        try:
            job.result = fn(job)
            job.status = "done"
        except _Cancelled:
            job.status = "cancelled"
        except RostrumError as e:
            job.status, job.reason = "failed", e.line()
        except Exception as e:                            # a bug in the job: say so, keep the traceback
            where = self._log(traceback.format_exc()) if self._log else "no log"
            job.status, job.reason = "failed", f"unexpected {type(e).__name__}: {e} (log: {where})"
        finally:
            job.finished.set()

    def get(self, job_id: str) -> Job:
        try:
            return self._jobs[job_id]
        except KeyError:
            raise RostrumError.not_found("", "job", job_id, self._jobs, "the jobs of this server (jobs end with the server in this stand-in)")

    def wait(self, job_id: str, wait_s: float) -> Job:
        job = self.get(job_id)
        job.finished.wait(min(max(wait_s, 0), MAX_WAIT_S))
        return job

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        job.cancel_requested.set()
        if job.status == "queued":                        # never started: stops at once
            job.status = "cancelled"
            job.finished.set()
        return job


def outcome(job: Job, where: str) -> Reply:
    """The reply for a job: the result when done, a progress line while it runs, an error when it failed or was stopped."""
    if job.status == "failed":
        raise RostrumError(codes.JOB_FAILED, where, job.id, f"({job.label}) failed: {job.reason}", hint="The job's output is incomplete; nothing was written.")
    if job.status == "cancelled":
        raise RostrumError(codes.JOB_INTERRUPTED, where, job.id, f"({job.label}) was stopped", hint="Its output is incomplete. Run it again if you still need it.")
    state = job.state()
    if job.status == "done":
        r = job.result
        return Reply(r.summary, {**state, "result": r.data}, r.files, r.images, r.warnings, r.changed)
    prog = f" {job.done} of {job.total}." if job.total else ""
    return Reply(f"Job {job.id} ({job.label}) is {job.status}.{prog} {job.note}".strip(), state)
