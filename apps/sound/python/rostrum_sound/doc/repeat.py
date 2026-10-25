"""Repeat × N for `<kind>.duplicate`: `times` copies, each `by` later, or as many as fit `until` a point (a time, a
"#marker", or {"section": "verse"} = that section's end). A copy that crosses the point is cut at it: a note is
shortened, a clip's length is shortened, a hit (no length) past it is left out. Never a copy past the point.
"""
from __future__ import annotations

from rostrum_core import Param, codes

from . import times
from . import values as V
from .select_time import delta, length_like, note_dur, speed, start_of

MAX = 64
TIMES = Param.number("times", min=1, max=MAX, integer=True, default=1, group="Move", label="Times", importance="secondary",
                     help=f"How many copies (1 … {MAX}), each `by` after the last. Left out = 1. With `until`: the most copies.")
SECTION_SCHEMA = {"type": "object", "properties": {"section": {"type": "string"}}, "required": ["section"]}


def _until(p, v, where):
    if isinstance(v, dict) and set(v) == {"section"} and isinstance(v["section"], str) and v["section"]:
        return v
    return V._time(p, v, where)


UNTIL = V.Value("until", "number", rule=_until, schema={"anyOf": [*V.TIME_SCHEMA["anyOf"], SECTION_SCHEMA]}, unit="s",
                form="time", group="Move", label="Until", importance="secondary",
                hint=V.TIME_HINT + ' {"section": "verse"} is the end of the section named verse.',
                help="Copy as many times as fit before this point; the last copy is cut at it (notes shortened, "
                     "drum hits past it left out). Never crosses it.")


def until_seconds(ctx, value) -> float:
    """Where `until` points, seconds. A section is found by its name (a missing one is a loud error listing them)."""
    if isinstance(value, dict):
        secs = ctx.doc.get("sections", [])
        hit = next((s for s in secs if str(s.get("name", "")).lower() == value["section"].lower()), None)
        if hit is None:
            ctx.fail(codes.NOT_FOUND, "until", f'section "{value["section"]}" is not in the song',
                     [s.get("name") for s in secs] or ["(the song has no sections)"])
        return times.seconds(hit["end"], ctx.doc, "until")
    return times.seconds(value, ctx.doc, "until")


def scaled(by, k: int):
    """`by` k times over (seconds, or {"beats": n})."""
    return {"beats": float(by["beats"]) * k} if isinstance(by, dict) else float(by) * k


def count(ctx, first: float, by, args) -> tuple[int, float | None]:
    """(copies, the point or None): `times`, or with `until` as many as start before the point (at most `times`, 64)."""
    if "until" not in args:
        return int(args.get("times", 1)), None
    point = until_seconds(ctx, args["until"])
    if delta(ctx.doc, first, by) <= 1e-6:
        ctx.fail(codes.BAD_ARGUMENT, "by", "must be later (positive) to copy until a point")
    cap = int(args.get("times", MAX))
    n = 0
    while n < cap and first + delta(ctx.doc, first, scaled(by, n + 1)) < point - 1e-6:
        n += 1
    if n == 0:
        ctx.fail(codes.BAD_ARGUMENT, "until", f"is at {point:.3f} s: no copy fits before it",
                 hint="Choose a later point, or copy without `until`.", plain="No copy fits before that point.")
    return n, point


def cut(ctx, kind: str, new: dict, end: float, point: float) -> dict | None:
    """The copy cut at `point` (its end then, seconds); None when it starts at or past the point."""
    root = ctx.doc
    start = start_of(root, new)
    if start >= point - 1e-6:
        return None
    if end <= point + 1e-6 or kind == "hit":
        return new
    if kind == "note":
        new["dur"] = note_dur(root, new, start, point) or round(point - start, 4)
    else:                                               # a clip: its length is seconds of the file
        new["length"] = length_like(new.get("length"), (point - start) * speed(new), root, start, new)
    return new
