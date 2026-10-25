"""What the "select, then act" operations share: moving a time by an amount, snapping one to a grid, where a
note / hit / clip starts and ends, and which ids a change brought in. Every new time is written in the form
the old one had (`shift.write_like`: seconds stay seconds, beats stay beats, a marker time keeps its marker with
a new offset), so there is one rule for "move a time by d" (the same one `section.move` uses).
"""
from __future__ import annotations

import dataclasses

from rostrum_core import RostrumError, codes
from rostrum_core import edits as E

from . import item_times, media, ops_music, tempo, times
from .shift import write_like

BY = dataclasses.replace(ops_music.BY, required=False, group="Move", label="By",
                         help='Seconds (2.5, -1) or {"beats": 1}: later is positive. Left out = right after the '
                              "selection's end (so a copy follows the original).")
BY_REQUIRED = dataclasses.replace(BY, required=True, help='Seconds (2.5, -1) or {"beats": 1}: later is positive.')
KINDS = {"note": "notes", "hit": "hits", "clip": "clips"}


def delta(root: dict, sec: float, by) -> float:
    """Seconds that `by` (seconds, or {"beats": n} from where `sec` is) comes to."""
    if isinstance(by, dict):
        return tempo.seconds_at(root, tempo.beat_at(root, sec) + float(by["beats"])) - sec
    return float(by)


def start_of(root: dict, item: dict) -> float:
    kept = item_times.span(root, item)            # a note's or a hit's, kept while it is the same item (item_times)
    return kept[0] if kept is not None else times.seconds(item["at"], root, item["id"])


def moved(ctx, item: dict, by, where: str | None = None):
    """The time `item["at"]` after moving by `by`, in its own form. Before the start of the song: a loud error."""
    sec = start_of(ctx.doc, item)
    to = sec + delta(ctx.doc, sec, by)
    if to < -1e-9:
        ctx.fail(codes.BAD_ARGUMENT, f'"{item["id"]}"', f"would start before the start of the song ({to:.3f} s)",
                 hint="Move it later, or move the whole selection less.",
                 plain="That would put it before the start of the song.")
    return write_like(item["at"], max(0.0, to), ctx.doc)


def at_seconds(ctx, item: dict, to: float):
    """`item["at"]` set to `to` seconds, in its own form (never before 0)."""
    return write_like(item["at"], max(0.0, to), ctx.doc)


def speed(item: dict) -> float:
    """How fast a clip plays its file: tape pitch speeds it up, stretch slows it down."""
    return 2 ** (float(item.get("pitch", 0)) / 12) / float(item.get("stretch", 1))


def source_length(item: dict, root: dict) -> float:
    """How much of a clip's file plays, seconds of the file (its length, or the rest of the file)."""
    if item.get("length") is not None:
        return times.length_seconds(item["length"], root, start_of(root, item), item, item["id"])
    return max(0.0, file_seconds(item) - float(item.get("in", 0)))


def file_seconds(item: dict) -> float:
    import soundfile as sf
    try:
        return float(sf.info(media.file(item["media"])).duration)
    except Exception as e:  # noqa: BLE001 - libsndfile's errors are plain RuntimeErrors
        raise RostrumError(codes.BAD_ARGUMENT, item["id"], f'media {item["media"]!r}',
                           f"could not be read to find its length ({e})", hint="Set the clip's length first.") from None


def clip_length(item: dict, root: dict) -> float:
    """How long a clip plays on the timeline, seconds."""
    return source_length(item, root) / speed(item)


def length_like(old, source_seconds: float, root: dict, start: float, item: dict):
    """A clip `length` of `source_seconds` of file, in the form `old` was written (beats stay beats while the clip
    plays at normal speed; anything else is seconds)."""
    if isinstance(old, dict) and "beats" in old and abs(speed(item) - 1) < 1e-9:
        return {"beats": round(tempo.beat_at(root, start + source_seconds) - tempo.beat_at(root, start), 4)}
    return round(source_seconds, 4)


def end_of(root: dict, item: dict) -> float:
    """Where a note / hit / clip ends, seconds (a hit ends where it starts; a note that can't tell, too)."""
    kept = item_times.span(root, item)
    if kept is not None:
        return kept[1]
    start = start_of(root, item)
    if item["type"] == "clip":
        return start + clip_length(item, root)
    if item["type"] == "note":
        try:
            return start + times.length_seconds(item["dur"], root, start, item, item["id"])
        except RostrumError:
            return start
    return start


def note_dur(root: dict, item: dict, new_start: float, new_end: float):
    """The note's `dur` for its new end, written like the old one (seconds or beats); None for a tied length."""
    dur = item["dur"]
    if dur == "next" or (isinstance(dur, dict) and "to" in dur):
        return None
    if isinstance(dur, dict):
        return {"beats": round(tempo.beat_at(root, new_end) - tempo.beat_at(root, new_start), 4)}
    return round(new_end - new_start, 4)


def inserted(change) -> list[str]:
    """The ids a change brought in, in order (the screen selects them after a duplicate or a split)."""
    return [e.id for e in change.edits if isinstance(e, E.Insert)]


def need_same_kind(ctx, targets, what: str):
    """All targets are on one track (join, crossfade): the track's id."""
    parents = {ctx.idx[t].parent for t in targets}
    if len(parents) != 1:
        ctx.fail(codes.BAD_ARGUMENT, "targets", f"are on {len(parents)} different tracks; {what} needs one track",
                 hint="Select clips of one track.")
    return parents.pop()


