"""Timing that single fields can't see, said in every reply (DocKind.warn) as soon as it happens, not first at render_mix.
Warnings, not refusals: a project marker moved in another app can cause either, and a song must still open.

- a tied note (`dur {"to": …}` / `"next"`) that ends at or before its start: the render refuses it;
- notes, hits and clips that start at or after the song's `length`: they are never heard;
- notes and clips held past it: they are let go at it (with Ring out they ring out from there, else they are cut).
One rule, the engine's (engine/src/contract/ending.rs): the render says the same in its `warnings`.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager

from rostrum_core import RostrumError

from . import item_times, times

SHOWN = 3
_HERE = threading.local()        # inside `same_song()`, per thread: (check, song) -> its words (a render thread's checks
                                 # never read the screen thread's block)


def _scope() -> list[dict]:
    if not hasattr(_HERE, "scope"):
        _HERE.scope = []
    return _HERE.scope


@contextmanager
def same_song():
    """Inside it each check runs once per song tree (the Problems list reads `ties` and `late` again to name the
    warnings `warn` gave): one read of the song, never kept past the block."""
    _scope().append({})
    try:
        yield
    finally:
        _scope().pop()


def _once(fn):
    def check(data: dict) -> list[str]:
        scope = _scope()
        if not scope:
            return fn(data)
        kept, key = scope[-1], (fn.__name__, id(data))
        if key not in kept:
            kept[key] = (data, fn(data))             # the song held, so its id is never another's inside the block
        return kept[key][1]
    check.__doc__ = fn.__doc__
    return check


def _start(data: dict, i: dict) -> float:
    kept = item_times.span(data, i)                 # kept per item (item_times): most items are unchanged since last time
    return kept[0] if kept is not None else times.seconds(i["at"], data, i["id"])


def _end(data: dict, n: dict, at: float) -> float:
    """A note's end seconds (it starts at `at`); a tie that ends before its start is a loud RostrumError."""
    kept = item_times.span(data, n)
    return kept[1] if kept is not None else at + times.length_seconds(n["dur"], data, at, n, n["id"])


@_once
def ties(data: dict) -> list[str]:
    out = []
    for t in data.get("tracks", []):
        for n in t.get("notes", []):
            d = n.get("dur")
            if d == times.NEXT or (isinstance(d, dict) and "to" in d):
                try:
                    times.length_seconds(d, data, times.seconds(n["at"], data, n["id"]), n, n["id"])
                except RostrumError as e:
                    out.append(f"{n['id']}: {e.subject} {e.problem}: render_mix refuses it until the note ends after it starts." + (f" {e.hint}" if e.hint else ""))
    return out


def warn(data: dict) -> list[str]:
    return ties(data) + late(data) + held(data)


RINGING_S = 0.5      # a sound still held (or just struck) this close to the end is cut off audibly


def hard_end(data: dict) -> str:
    """The song stops dead on sound: its soft end (`endFade`) is off and a note is still held, or a hit or clip still
    sounds, in its last half second. "" when not (or when it ends after the last sound: no `length`)."""
    if data.get("length") is None or data.get("ringOut") or data.get("endFade", True):
        return ""
    try:
        end = times.seconds(data["length"], data, "length")
        for t in data.get("tracks", []):
            for n in t.get("notes", []):
                at = _start(data, n)
                if at < end and _end(data, n, at) > end - RINGING_S:
                    return n["id"]
            for h in t.get("hits", []):
                if end - RINGING_S < _start(data, h) < end:
                    return h["id"]
            for c in t.get("clips", []):          # a clip with no length plays to its file's end: taken as still playing
                at = times.seconds(c["at"], data, c["id"])
                if at < end and (c.get("length") is None or at + times.length_seconds(c["length"], data, at) > end - RINGING_S):
                    return c["id"]
    except RostrumError:
        return ""                                    # a broken time is the check's to report
    return ""


@_once
def late(data: dict) -> list[str]:
    if data.get("length") is None:
        return []
    try:
        end = times.seconds(data["length"], data, "length")
        late = [(i["id"], s) for t in data.get("tracks", []) for k in ("notes", "hits", "clips")
                for i in t.get(k, []) if (s := _start(data, i)) >= end - 1e-6]
    except RostrumError:
        return []                                    # a broken time is the check's to report
    if not late:
        return []
    shown = ", ".join(f"{i} at {s:.2f} s" for i, s in late[:SHOWN]) + (f" and {len(late) - SHOWN} more" if len(late) > SHOWN else "")
    return [f"{len(late)} note(s), hit(s) or clip(s) start at or after the song's end ({end:.2f} s) and are never heard: {shown}. "
            "Move them earlier or make the song longer (length)."]


@_once
def held(data: dict) -> list[str]:
    if data.get("length") is None:
        return []
    try:
        end = times.seconds(data["length"], data, "length")
        over = []
        for t in data.get("tracks", []):
            for n in t.get("notes", []):
                at = _start(data, n)
                if at < end - 1e-6 and _end(data, n, at) > end + 1e-6:
                    over.append((n["id"], at))
            for c in t.get("clips", []):
                at = times.seconds(c["at"], data, c["id"])
                if c.get("length") is not None and at < end - 1e-6 < at + times.length_seconds(c["length"], data, at):
                    over.append((c["id"], at))
    except RostrumError:
        return []                                    # a broken time is the check's to report
    if not over:
        return []
    shown = ", ".join(f"{i} at {s:.2f} s" for i, s in over[:SHOWN]) + (f" and {len(over) - SHOWN} more" if len(over) > SHOWN else "")
    how = "ring out from there" if data.get("ringOut") else "are cut off (Ring out is off)"
    return [f"{len(over)} note(s) or clip(s) are held past the song's end ({end:.2f} s): they are let go there and {how}: "
            f"{shown}. Shorten them or make the song longer (length) if they should be heard whole."]
