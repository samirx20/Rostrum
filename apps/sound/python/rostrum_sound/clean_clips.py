"""A document's clips and their cleaned takes: the one place that knows which cached take a clip plays.

The clip holds its original `media` and its cleanup settings (doc/fields_cleanup.py); the cache holds the cleaned
take (`cleanup/`). `compile.py` plays `media_of(clip)`, which fails loudly where the take is not made yet;
`make_clips` makes the missing takes, one clip at a time (each step's model loads for it and is released), for
the `render_cleanup` tool and the screen.

A clip's `media` is resolved by `doc/media.py` (relative: under the project folder; absolute: as written); a missing file
is a loud error naming the clip, its track and the file. The cleaned take is found by the file's content, so either form finds the same take.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes

from . import cleanup
from .doc import media

HINT = ("On the Timeline: select the clip and press Make cleaned take, or turn its Use cleaned take off. "
        "Agents: run the render_cleanup tool, or set useCleaned false (clip.set).")


def media_of(clip: dict, where: str) -> str:
    """The file the clip plays: its cleaned take while it needs one, else its own media."""
    path = media.file(clip["media"])
    if not media.exists(path):
        raise RostrumError(codes.NOT_FOUND, where, f'clip "{clip["id"]}"\'s file {clip["media"]}', "is missing",
                           hint="Put the file back (a take is in the project's media folder), or swap the clip's sound (clip.swap).")
    if not cleanup.needs_cleanup(clip):
        return path
    made = cleanup.cached(path, cleanup.recipe_of(clip))
    if made is None:
        raise RostrumError(codes.NOT_FOUND, where, f'clip "{clip["id"]}"\'s cleaned take', "is not made yet",
                           hint=HINT)
    return made


def played_file(clip: dict) -> str:
    """The file a screen draws the clip from: the cleaned take when the clip plays one, else its own media (no error: a take
    not made yet plays the original meanwhile, see without_pending). One source for what the clip plays and what it shows."""
    path = media.file(clip["media"])
    if cleanup.needs_cleanup(clip):
        return cleanup.cached(path, cleanup.recipe_of(clip)) or path
    return path


def pending(doc) -> list[str]:
    """The ids of clips that need a cleaned take which is not made yet."""
    with media.of(doc):
        return [c["id"] for _, c in clips(doc) if cleanup.cached(media.file(c["media"]), cleanup.recipe_of(c)) is None]


def without_pending(doc):
    """The document as a *playing* screen reads it: a clip whose cleaned take is not made yet plays its original
    meanwhile (the screen says the take is pending and re-renders when it lands). Never used by export or the MCP
    render, which fail loudly rather than ship the wrong sound."""
    ids = pending(doc)
    if not ids:
        return doc
    import copy
    from types import SimpleNamespace
    data = copy.deepcopy(doc.data)
    for t in data.get("tracks", []):
        for c in t.get("clips", []):
            if c["id"] in ids:
                c["useCleaned"] = False
    return SimpleNamespace(data=data, folder=getattr(doc, "folder", None))


def clips(doc, ids=None) -> list[tuple[dict, dict]]:
    """(track, clip) for the given clip ids, or every clip that plays a cleaned take; an unknown id is a loud error,
    and so is a given clip with no cleanup step set."""
    root = getattr(doc, "data", doc)
    found = [(t, c) for t in root.get("tracks", []) for c in t.get("clips", [])]
    known = [c["id"] for _, c in found]
    for i in ids or ():
        if i not in known:
            raise RostrumError.not_found("render_cleanup", "clip", i, known)
    if ids:
        picked = [(t, c) for t, c in found if c["id"] in ids]
        for _, c in picked:
            if not cleanup.recipe_of(c):
                raise RostrumError(codes.BAD_ARGUMENT, "render_cleanup", f'clip "{c["id"]}"', "has no cleanup step set",
                                   hint="Set its stem, isolate, denoise or dereverb first (clip.set).")
        return picked
    return [(t, c) for t, c in found if cleanup.needs_cleanup(c)]


def make_clips(doc, ids=None, progress=None) -> list[dict]:
    """Make every missing cleaned take (of all clips that play one, or the given ids); one answer per clip, in
    document order: id, track, media (the original), file (the cleaned take), generated, steps."""
    out = []
    with media.of(doc):
        for t, c in clips(doc, ids):
            if progress:
                progress(f'{c["id"]}: {c["media"]}')
            try:
                r = cleanup.make(media.file(c["media"]), cleanup.recipe_of(c),
                                 progress=(lambda note, i=c["id"]: progress(f"{i}: {note}")) if progress else None)
            except RostrumError as e:
                raise RostrumError(e.code, f"clip {c['id']}", e.subject, e.problem, hint=e.hint) from e
            out.append({"id": c["id"], "track": t["id"], "media": c["media"], "file": r.file, "generated": r.generated,
                        "steps": r.steps})
    return out
