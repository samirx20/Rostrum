"""Scripted steps for the Export panel's save-to path and its "Replace?" question (steps.py hands these over).

    exportto <path> [replace|both|cancel]  choose where to save, press Export; the answer (default: none, the question stays
                                           open for a screenshot), then wait for the job when it started
    exportshow                             press "Show in folder" (starts the file manager)
Paths: _ for spaces.
"""
from __future__ import annotations

WORDS = ("exportto", "exportshow")


def do_export_step(bridge, word, rest, step):
    job = bridge.exporter
    if word == "exportshow":
        return job.showInFolder()
    job.setTarget(rest[0].replace("_", " "))
    job.request()
    if rest[1:] and job._asked:
        job.answer(rest[1])
    if job.state == "running" and not job.wait(600):
        raise RuntimeError(f"step {step!r}: the export did not finish in 10 minutes")
    if job.state in ("failed",):
        raise RuntimeError(f"step {step!r}: {job.note}")
