"""Learning from the last real render: how far off the guess was, kept in this process for the same project, item, shot and
renderer. The probe (estimate_job) cannot see everything a long render pays (round 3 of the 3D gaps: a cloth drape was guessed
at 532 s and took 876 s), so after a render that drew every frame, the real time over the guess is kept, and the next guess for
that shot is raised by it, and says so. Only ever raised, never lowered ("never promise fit when unsure"), and held under CAP.
"""
from __future__ import annotations

MIN_OFF = 1.1       # a render under 10 % over its guess teaches nothing
CAP = 3.0
_LAST: dict[tuple, float] = {}


def key(folder, item, shot: str, renderer: str) -> tuple:
    return (str(folder), item, shot, renderer)


def record(k: tuple, guessed_s: float | None, took_s: float):
    """After a render that drew all its frames: the real seconds over the guess, or forgotten when it was close or under."""
    if not guessed_s or guessed_s <= 0 or took_s <= 0:
        return
    off = took_s / guessed_s
    if off >= MIN_OFF:
        _LAST[k] = min(off, CAP)
    else:
        _LAST.pop(k, None)


def factor(k: tuple) -> float:
    return _LAST.get(k, 1.0)


def apply(e: dict, k: tuple) -> dict:
    """An estimate (estimate.scale's dict) raised by what the last render of this shot taught; unchanged when nothing was learned."""
    f = factor(k)
    if f <= 1.0:
        return e
    from .mcp.estimate import sheet_text
    sec = round(e["seconds"] * f, 1)
    return {**e, "seconds": sec, "seconds_per_frame": round(e["seconds_per_frame"] * f, 3), "learned": round(f, 2),
            "text": sheet_text(sec, e["frames"], e["seconds_per_frame"] * f)}


def words(e: dict) -> str:
    return (f"raised ×{e['learned']:g}: the last render of this shot took that much longer than its estimate" if e.get("learned") else "")
