"""Everything wrong with a song, as one list: what inspect_diagnose returns and the screen's Problems chip shows.
Each problem: {kind, item, message, fix}. Read-only. The checks come from the pieces that already decide each thing:
the shared file rule (rostrum_core.project.media_problems: missing and outside files), the cleaned-take cache
(cleanup.cached) and the song's warnings (DocKind.warn: designed sounds no longer made)."""
from __future__ import annotations

from rostrum_core import project as P

from . import clean_clips, cleanup
from .doc import media, past_end

# every kind of problem and its name on the chip: ONE list (the chip never looks a kind up anywhere else)
LABELS = {"missing-file": "Missing file", "outside-project": "File outside the song", "pending-take": "Cleaned take not made",
          "broken-tie": "Note ends before it starts", "after-the-end": "Sounds after the end", "no-longer-made": "No longer made"}
KINDS = tuple(LABELS)


def said(found: list[dict]) -> str:
    """The list as one line for an agent: the same problem on several things is one entry naming each (with its id)."""
    groups: dict = {}
    for p in found:
        groups.setdefault((p["kind"], p["message"]), []).append(p["item"])
    return "; ".join(f'{k}: {m}' + (f' ({", ".join(i for i in items if i)})' if any(i and i not in m for i in items) else "") for (k, m), items in groups.items())


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
    ties, late = past_end.ties(doc.data), past_end.late(doc.data)
    for w in doc.kind.warnings(doc.data):
        kind = "broken-tie" if w in ties else "after-the-end" if w in late else "no-longer-made"
        fix = {"broken-tie": "End it later or give it a length (the message says how)", "after-the-end": "Move them earlier or make the song longer",
               "no-longer-made": "Remove it or replace it with an instrument"}[kind]
        out.append({"kind": kind, "item": w.split(":", 1)[0] if ":" in w and kind != "after-the-end" else "", "message": w, "fix": fix})
    return out
