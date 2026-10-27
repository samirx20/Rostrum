"""Jobs for long work: a small in-process stand-in for the project service's one queue (CONVENTIONS § 7).

The real queue (shared/project-service/CONTRACT.md) swaps in behind `Jobs`: same four calls, same job fields.
Other programs see a waiting or running job, and can stop it, through its job file (job_files.py).
A job's function runs in a worker thread and must NOT touch the document: it returns a Reply, and the
document changes only through an operation afterwards (OPERATIONS.md § 1).
"""
from __future__ import annotations

import threading
import time
import traceback
import uuid
from typing import Callable, Protocol

from .. import bug
from ..errors import RostrumError, codes
from . import job_files
from .reply import Reply

MAX_WAIT_S = 25
WAITING, RUNNING = "queued", "running"
ENDED = ("done", "failed", "cancelled")


class Job:
    def __init__(self, label: str, key: str | None):
        self.id = "job_" + uuid.uuid4().hex[:6]          # unique across programs too (job_files.py)
        self.label, self.key = label, key
        self.status = WAITING                   # queued | running | done | failed | cancelled
        self.done = self.total = None
        self.note = ""
        self.result: Reply | None = None
        self.reason = ""
        self.started = self.ended = None        # time.monotonic() when it began and ended (None: not yet)
        self.stepped = None                     # time.monotonic() of the last progress step (a stall shows as it grows)
        self.owner = None                       # another program's process id (a job seen through its file), else None
        self.changed = None                     # callable(job), told of each step (the queue writes the job file)
        self.cancel_requested = threading.Event()
        self.finished = threading.Event()
        self._stops: list[Callable[[], None]] = []

    def progress(self, done=None, total=None, note: str = ""):
        """Called by the job's function. Also the place a long job notices a stop request."""
        self.done, self.total, self.note = done, total, note
        self.stepped = time.monotonic()
        if self.changed:
            self.changed(self)
        if self.cancel_requested.is_set():
            raise _Cancelled()

    def on_cancel(self, fn: Callable[[], None]):
        """A stop hook: cancel() calls it while the job runs (e.g. end the job's own engine process by its handle).
        Registered after a cancel was asked for, it runs at once."""
        self._stops.append(fn)
        if self.cancel_requested.is_set():
            fn()

    def seconds(self) -> float | None:
        """How long it has run (or ran); None before it starts."""
        return None if self.started is None else (self.ended or time.monotonic()) - self.started

    def state(self) -> dict:
        out = {"job_id": self.id, "label": self.label, "status": self.status, "note": self.note}
        if self.total:
            out["progress"] = {"done": self.done, "total": self.total}
            if self.stepped is not None and self.status == RUNNING:
                out["progress"]["last_step_s_ago"] = round(time.monotonic() - self.stepped, 1)
        if self.owner:
            out["program"] = self.owner
        if self.reason:
            out["reason"] = self.reason
        return out


class _Cancelled(Exception):
    pass


def _seen(state: dict) -> Job:
    """Another program's job, as read from its file: a snapshot (its own program runs it)."""
    job = Job(state.get("label", ""), None)
    job.id, job.status, job.note, job.reason, job.owner = state["job_id"], state["status"], state.get("note", ""), state.get("reason", ""), state.get("pid")
    prog = state.get("progress") or {}
    job.done, job.total = prog.get("done"), prog.get("total")
    if prog.get("last_step_s_ago") is not None:            # as written, plus the time since it was written
        job.stepped = time.monotonic() - prog["last_step_s_ago"] - max(0.0, time.time() - state.get("updated", time.time()))
    if job.status in ENDED:
        job.finished.set()
    return job


class Jobs(Protocol):
    def submit(self, label: str, fn: Callable[[Job], Reply], key: str | None = None) -> Job: ...
    def get(self, job_id: str) -> Job: ...
    def wait(self, job_id: str, wait_s: float) -> Job: ...
    def cancel(self, job_id: str) -> Job: ...


class InProcessJobs:
    """One ordered list of jobs, run in order by `workers` worker threads (1: one heavy job at a time). The waiting ones
    can be reordered (`move`); `listing()` gives them all in order: running, waiting, then the ended ones."""

    def __init__(self, workers: int = 1, log=None, shared: bool = True):
        self._order: list[Job] = []                       # submit order; `move` reorders the waiting ones
        self._fns: dict[str, Callable] = {}
        self._jobs: dict[str, Job] = {}
        self._cv = threading.Condition()
        self._log = log                                   # callable(text) -> log path, for unexpected failures
        self._workers, self._running = workers, 0
        self._shared = shared                             # write job files so other programs see and can stop the jobs
        self._written: dict[str, float] = {}              # job id -> when its file was last written (steps: once a second)

    def submit(self, label, fn, key=None) -> Job:
        with self._cv:
            for j in self._order:                         # the same work again joins the running job
                if key and j.key == key and j.status in (WAITING, RUNNING):
                    return j
            job = Job(label, key)
            self._jobs[job.id], self._fns[job.id] = job, fn
            self._order.append(job)
            self._publish(job, force=True)
            if self._running < self._workers:
                self._running += 1
                threading.Thread(target=self._worker, name="rostrum-job", daemon=True).start()
            self._cv.notify()
        return job

    def _worker(self):
        while True:
            with self._cv:
                job = next((j for j in self._order if j.status == WAITING), None)
                if job is None:
                    self._running -= 1                    # no work: this thread ends (a new submit starts one)
                    return
                job.status, job.started = RUNNING, time.monotonic()
                fn = self._fns.pop(job.id)
            self._publish(job, force=True)
            if self._shared:
                job_files.watch(job, self.cancel)         # a stop asked by another program
            self._run(job, fn)

    def _run(self, job: Job, fn):
        try:
            job.result = fn(job)
            job.status = "done"                           # it finished its work (a stop asked for too late changes nothing)
        except Exception as e:                            # noqa: BLE001  every way out is named, never a quiet "done"
            if job.cancel_requested.is_set():             # stopped on purpose (its stop hook ended its process): not a failure
                job.status, job.reason = "cancelled", "cancelled"
            elif isinstance(e, RostrumError):
                job.status, job.reason = "failed", e.line()
            else:                                         # a bug in the job: say so, keep the traceback
                where = self._log(traceback.format_exc()) if self._log else "no log"
                job.status, job.reason = "failed", f"unexpected {bug.said(e)} (log: {where})"
        finally:
            job.ended = time.monotonic()
            job.finished.set()
            if self._shared:
                job_files.remove(job.id)

    def _publish(self, job: Job, force: bool = False):
        """Write the job's file for other programs (a step at most once a second)."""
        if not self._shared or job.status in ENDED:
            return
        job.changed = self._publish
        now = time.monotonic()
        if force or now - self._written.get(job.id, 0) >= 1.0:
            self._written[job.id] = now
            job_files.write(job.state())

    def get(self, job_id: str) -> Job:
        try:
            return self._jobs[job_id]
        except KeyError:
            state = job_files.read(job_id) if self._shared else None
            if state is None:
                raise RostrumError.not_found("", "job", job_id, self._jobs, "the jobs of this server, and the ones other programs have waiting or running") from None
            return _seen(state)

    def wait(self, job_id: str, wait_s: float) -> Job:
        job = self.get(job_id)
        until = time.monotonic() + min(max(wait_s, 0), MAX_WAIT_S)
        while job.owner and not job.finished.is_set() and time.monotonic() < until:   # another program's: read its file again
            time.sleep(0.5)
            try:
                job = self.get(job_id)
            except RostrumError:                          # its file went: the job ended there (its result stays with that program)
                job.status, job.note = "done", f"ended in its program (process {job.owner}); ask that program for its result"
                job.finished.set()
        job.finished.wait(max(0.0, until - time.monotonic()))
        return job

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        if job.owner:                                     # another program's job: asked through its file
            job_files.ask_stop(job_id)
            job.note = f"stop asked; its program (process {job.owner}) stops it within a few seconds"
            return job
        with self._cv:
            job.cancel_requested.set()
            if job.status == WAITING:                     # never started: stops at once
                job.status, job.reason, job.ended = "cancelled", "cancelled before it started", time.monotonic()
                self._fns.pop(job.id, None)
                job.finished.set()
            stops = list(job._stops) if job.status == RUNNING else []
        for fn in stops:                                  # outside the lock: a hook may wait for its process
            fn()
        return job

    def move(self, job_id: str, index: int) -> Job:
        """Put a waiting job at `index` among the waiting ones (0 = next to run). A running or ended one can't move."""
        job = self.get(job_id)
        with self._cv:
            if job.status != WAITING:
                raise RostrumError(codes.BAD_ARGUMENT, "jobs.move", job.id, f"is {job.status}; only a waiting job can move")
            waiting = [j for j in self._order if j.status == WAITING and j is not job]
            index = min(max(int(index), 0), len(waiting))
            waiting.insert(index, job)
            others = [j for j in self._order if j.status != WAITING]
            self._order = others + waiting
        return job

    def listing(self) -> list[Job]:
        """Every job in order: the running ones, the waiting ones (in the order they will run), then the ended ones,
        newest first."""
        with self._cv:
            rank = {RUNNING: 0, WAITING: 1}
            live = sorted((j for j in self._order if j.status in rank), key=lambda j: rank[j.status])   # sorted here: a job ending later can't fall out of `rank`
            ended = sorted((j for j in self._order if j.status in ENDED), key=lambda j: -(j.ended or 0))
        others = [_seen(s) for s in job_files.others()] if self._shared else []
        return live + others + ended


def outcome(job: Job, where: str) -> Reply:
    """The reply for a job: the result when done, a progress line while it runs, an error when it failed or was stopped."""
    if job.status == "failed":
        raise RostrumError(codes.JOB_FAILED, where, job.id, f"({job.label}) failed: {job.reason}", hint="The job's output is incomplete; nothing was written.")
    if job.status == "cancelled":
        raise RostrumError(codes.JOB_INTERRUPTED, where, job.id, f"({job.label}) was stopped", hint="Its output is incomplete. Run it again if you still need it.")
    state = job.state()
    if job.status == "done" and job.owner:            # another program's: its result stays there
        return Reply(f"Job {job.id} ({job.label}) {job.note}.", state)
    if job.status == "done":
        r = job.result
        return Reply(r.summary, {**state, "result": r.data}, r.files, r.images, r.warnings, r.changed)
    prog = f" {job.done} of {job.total}." if job.total else ""
    if job.total and job.status == RUNNING and job.stepped is not None and time.monotonic() - job.stepped >= 10:
        prog += f" Nothing new for {time.monotonic() - job.stepped:.0f} s (a stuck frame fails the job by itself after its limit)."
    if job.owner:
        prog += f" It runs in another program (process {job.owner})."
    return Reply(f"Job {job.id} ({job.label}) is {job.status}.{prog} {job.note}".strip(), state)
