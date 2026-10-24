"""Everything wrong with a song, as one list: what inspect_diagnose returns and the screen's Problems chip shows.
Each problem: {kind, item, message, fix}. Read-only. The checks come from the pieces that already decide each thing:
the shared file rule (rostrum_core.project.media_problems: missing and outside files), the cleaned-take cache
(cleanup.cached) and the song's warnings (DocKind.warn: designed sounds no longer made)."""
from __future__ import annotations

from rostrum_core import project as P

from . import clean_clips, cleanup
from .doc import media

KINDS = ("missing-file", "outside-project", "pending-take", "no-longer-made")


def _called(root: dict, track: dict) -> str:
    """The track as words: track "Drums", else "track 3" (an id never shows)."""
    if track.get("name"):
        return f'track "{track["name"]}"'
    return f'track {[t["id"] for t in root.get("tracks", [])].index(track["id"]) + 1}'


def problems(doc) -> list[dict]:
    clips = [(t, c) for t in doc.data.get("tracks", []) for c in t.get("clips", [])]
    refs = [(c["id"], f"the clip on {_called(doc.data, t)}", c["media"]) for t, c in clips if isinstance(c.get("media"), str)]
    out = P.media_problems(getattr(doc, "folder", None), refs)
    for p in out:                                    # the row's `item` names the clip for an agent; the words never show the id
        p["message"] = p["message"].replace(f" ({p['item']})", "", 1)
    gone = {p["item"] for p in out if p["kind"] == "missing-file"}     # a missing file's take can't be looked up
    with media.of(doc):
        waiting = [(c["id"], t) for t, c in clean_clips.clips(doc) if c["id"] not in gone
                   and cleanup.cached(media.file(c["media"]), cleanup.recipe_of(c)) is None]
    out += [{"kind": "pending-take", "item": i, "message": f"The clip on {_called(doc.data, t)} needs a cleaned take that is not made yet; until it is, "
             "the original plays", "fix": clean_clips.HINT}
            for i, t in waiting]
    out += [{"kind": "no-longer-made", "item": w.split(":", 1)[0] if ":" in w else "", "message": w,
             "fix": "Remove it or replace it with an instrument"} for w in doc.kind.warnings(doc.data)]
    return out
