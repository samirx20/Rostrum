"""A script that writes its music in seconds: said in run_script's reply, because a tempo change then moves nothing.

Notes and drum hits count (clips are recordings, placed in seconds on purpose); a time is "in seconds" when it is a bare
number, and on the music when it is a beat (bar(), beat()) or a marker ("#drop"). Said when a script writes at least
MIN_NOTES of them and SHARE or more are in seconds.
"""
from __future__ import annotations

from .script_scope import say

MIN_NOTES = 8
SHARE = 0.9


def in_seconds(at) -> bool:
    return isinstance(at, (int, float)) and not isinstance(at, bool)


def check(song) -> None:
    times = [f["at"] for t in song.tracks for _, f, _ in (*t.notes, *t.hits)]
    secs = sum(in_seconds(at) for at in times)
    if len(times) >= MIN_NOTES and secs >= SHARE * len(times):
        which = "all" if secs == len(times) else f"{secs} of"
        say(f"{which} {len(times)} notes and hits are in seconds (at=12.5): a tempo change won't move them. Write them "
            "with bar()/beat() (at=bar(5) + beats(1)), and seconds only for sync points (a marker, \"#hit\").")
