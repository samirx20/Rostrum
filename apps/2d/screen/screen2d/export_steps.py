"""Scripted steps for the Export sheet's Browse folder and its "already there" question (steps.py hands these over).

    exportto <folder> [replace|both|cancel]  Browse to that folder, press Export; the answer (default: none, the question
                                           stays open for a screenshot), then wait for the job when it started
    exportshow                             press "Show in folder" (starts the file manager)
    exportsize                             wait for the GIF's measured size to show on the sheet (gif_guess.py)
Paths: _ for spaces.
"""
from __future__ import annotations

WORDS = ("exportto", "exportshow", "exportsize")


def do_export_step(bridge, word, rest, step):
    job = bridge.exporter
    if word == "exportshow":
        return job.showInFolder()
    if word == "exportsize":
        job.settings                                   # (read: starts the measuring when nothing has asked yet)
        if not job.guess.wait(60):
            raise RuntimeError(f"step {step!r}: the GIF's size was not worked out in a minute")
        return None
    job.setFolder(rest[0].replace("_", " "))
    job.request()
    if rest[1:] and job.asking():
        job.answer(rest[1])
    if job.state == "running" and not job.wait(600):
        raise RuntimeError(f"step {step!r}: the export did not finish in 10 minutes")
    if job.state in ("failed",):
        raise RuntimeError(f"step {step!r}: {job.note}")
