"""A render waits for the song's edit jobs asked before it (3E audit: edit_loudness queued a job, the next render_mix
ran on the song as it was and landed under the target again). The jobs that change a song are named "<what> <item>";
the render notes the ones waiting or running when it is asked, and its job waits for them before it compiles the song.
A wait past WAIT_S fails the render loudly, naming the job, never renders the old song."""
from __future__ import annotations

import time

from rostrum_core import RostrumError, codes
from rostrum_core.mcp.jobs import RUNNING, WAITING

EDITS = ("edit_loudness", "cleanup", "voice", "voice words")     # the job labels (before the item id) that change a song
WAIT_S = 300.0


def pending(jobs, item: str) -> list:
    """This server's jobs that edit `item` and have not ended yet."""
    names = {f"{w} {item}" for w in EDITS}
    try:
        try:
            live = jobs.listing(others=False)     # its own: other programs' job files are never this song's edits
        except TypeError:                          # a queue that lists only its own
            live = jobs.listing()
    except AttributeError:             # a job queue that cannot list: nothing known to wait for
        return []
    return [j for j in live if j.owner is None and j.label in names and j.status in (WAITING, RUNNING)]


def wait(found: list, where: str, wait_s: float = WAIT_S) -> list[str]:
    """Wait for each job in `found` (the list `pending` gave); -> words for each one that did not finish its edit."""
    until = time.monotonic() + wait_s
    said = []
    for j in found:
        if not j.finished.wait(max(0.0, until - time.monotonic())):
            raise RostrumError(codes.JOB_FAILED, where, f"job {j.id} ({j.label})",
                               f"was still {j.status} after {wait_s:g} s, so the song it edits was not rendered",
                               hint=f'Wait for it (inspect_job {{"job": "{j.id}"}}) or stop it (run_stop), then render again.')
        if j.status != "done":
            said.append(f"{j.label} ({j.id}) {j.status}: {j.reason or 'no reason given'}; rendered without its edit.")
    return said
