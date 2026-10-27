"""A voice track's lines as audio: the one place that knows which cached take belongs to a line.

The document holds the recipe (words, voice, style, language, take number); the cache holds the audio
(`voice.py`). `compile.py` turns each line into a clip on its cached take and fails loudly where there is none;
`make_lines` makes the missing takes, one at a time (the voice model loads for a line and is released), for the
`render_voice` tool and the screen's Make voice.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes

from . import voice, voice_estimate
from .doc import times

CLIP_KEYS = ("volume", "fadeIn", "fadeOut")


def _recipe(track: dict, line: dict) -> dict:
    return dict(text=line["text"], voice=track.get("voice", "ryan"), style=track.get("style", ""),
                language=track.get("language", "auto"), seed=line.get("seed", 1))


def take_of(track: dict, line: dict):
    """The line's cached take, or None when it has not been made."""
    return voice.cached(**_recipe(track, line))


def clip_of(track: dict, line: dict, at) -> dict:
    """The line as a schedule clip on its take; a loud error naming the line when the take is not made yet."""
    take = take_of(track, line)
    if take is None:
        raise RostrumError(codes.NOT_FOUND, f"tracks[{track['id']}].lines[{line['id']}]", f'voice line "{line["id"]}"',
                           "is not made yet", hint="Run the render_voice tool, or type the line in the Editor (it is spoken at once).")
    return {"media": take.file, "at": at, **{k: line[k] for k in CLIP_KEYS if k in line}}


def lines(doc, ids=None) -> list[tuple[dict, dict]]:
    """(track, line) for the given line ids, or every line; an unknown id is a loud error."""
    root = getattr(doc, "data", doc)
    found = [(t, ln) for t in root.get("tracks", []) for ln in t.get("lines", [])]
    known = [ln["id"] for _, ln in found]
    for i in ids or ():
        if i not in known:
            raise RostrumError.not_found("voice", "line", i, known)
    return [(t, ln) for t, ln in found if not ids or ln["id"] in ids]


def is_made(doc, ids=None) -> bool:
    return all(take_of(t, ln) for t, ln in lines(doc, ids))


def estimates(doc, ids=None) -> list[dict]:
    """How long each line will take, before it is made: id, track, text, estimated_seconds with low and high
    (`voice_estimate`), and `made_seconds` when its take already exists (then that is exact, and so is `end`)."""
    root, out = getattr(doc, "data", doc), []
    for t, ln in lines(doc, ids):
        e = voice_estimate.estimate(ln["text"], t.get("language", "auto"))
        take = take_of(t, ln)
        start = times.seconds(ln["at"], root, f"line {ln['id']}")
        row = {"id": ln["id"], "track": t["id"], "text": ln["text"], "start": round(start, 3),
               "estimated_seconds": e["seconds"], "low": e["low"], "high": e["high"], "made_seconds": round(take.seconds, 3) if take else None}
        row["ends_about"] = round(start + (take.seconds if take else e["seconds"]), 2)
        out.append(row)
    return out


def make_lines(doc, ids=None, progress=None) -> list[dict]:
    """Make every missing take (of all lines, or the given ids); one answer per line, in document order:
    id, track, text, file, seconds, generated, start, end (when the line ends, so the next can be timed)."""
    root, out = getattr(doc, "data", doc), []
    for t, ln in lines(doc, ids):
        if progress:
            progress(f'{ln["id"]}: "{ln["text"][:40]}"')
        try:
            take = voice.generate(**_recipe(t, ln))
        except RostrumError as e:
            raise RostrumError(e.code, f"voice line {ln['id']}", e.subject, e.problem, hint=e.hint) from e
        start = times.seconds(ln["at"], root, f"line {ln['id']}")
        out.append({"id": ln["id"], "track": t["id"], "text": ln["text"], "file": take.file,
                    "seconds": round(take.seconds, 3), "generated": take.generated, "start": round(start, 3),
                    "end": round(start + take.seconds, 3)})
    return out
