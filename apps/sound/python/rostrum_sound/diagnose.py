"""Everything wrong with a song, as one list: what inspect_diagnose returns and the screen's Problems chip shows.
Each problem: {kind, item, message, fix}. Read-only. The checks come from the pieces that already decide each thing:
the shared file rule (rostrum_core.project.media_problems: missing and outside files), the cleaned-take cache
(cleanup.cached), the song's warnings (DocKind.warn: designed sounds no longer made) and, given the sound engine, notes a
track's recorded sound can't play (note_ranges: the render would refuse the whole song)."""
from __future__ import annotations

from typing import Iterator

from rostrum_core import project as P

from . import clean_clips, cleanup, note_ranges
from .doc import item_times, media, past_end

# every kind of problem and its name on the chip: ONE list (the chip never looks a kind up anywhere else)
LABELS = {"missing-file": "Missing file", "outside-project": "File outside the song", "pending-take": "Cleaned take not made",
          "broken-tie": "Note ends before it starts", "after-the-end": "Sounds after the end", "held-past-end": "Held past the end",
          "no-longer-made": "No longer made",
          "hard-end": "Stops dead at the end", "out-of-range": "Notes it can't play"}
KINDS = tuple(LABELS)
FIXES = {"broken-tie": "End it later or give it a length (the message says how)", "after-the-end": "Move them earlier or make the song longer",
         "held-past-end": "Shorten them or make the song longer if they should be heard whole (or turn on Ring out to let them ring)",
         "no-longer-made": "Remove it or replace it with an instrument",
         "out-of-range": "Move those notes into its range (Up or Down an octave) or pick another sound"}
_OUTSIDE: dict = {}         # (folder, item, name, path) -> the shared rule's outside-project rows for that file (see _files)


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


def problems(doc, engine=None) -> list[dict]:
    out: list[dict] = []
    for _ in steps(doc, out, engine):
        pass
    return out


STEP = 400          # items whose times are worked out in one step (~2-4 ms), clips whose files are looked at: 8


def steps(doc, out: list, engine=None) -> Iterator[None]:
    """`problems(doc)` in small steps, the list growing in `out` (complete when it ends): the screen's Problems chip
    runs it between events, so checking a whole song after a whole-song Right never holds up a key. Read only; the
    song is read as it was when it began (a change starts a new run: the screen drops the old one)."""
    data, folder = doc.data, getattr(doc, "folder", None)
    clips = [(t, c) for t in data.get("tracks", []) for c in t.get("clips", [])]
    refs = [(c["id"], f"the clip on {_called(data, t)}", c["media"]) for t, c in clips if isinstance(c.get("media"), str)]
    found: list[dict] = []
    for n in range(0, len(refs), 8):                 # each file is looked for on disk: a few at a time
        found += _files(folder, refs[n:n + 8])
        yield
    for p in found:                                  # the row's `item` names the clip for an agent; the words never show the id
        p["message"] = p["message"].replace(f" ({p['item']})", "", 1)
    out += found
    gone = {p["item"] for p in found if p["kind"] == "missing-file"}     # a missing file's take can't be looked up
    with media.of(doc):
        waiting = [(c["id"], t) for t, c in clean_clips.clips(doc) if c["id"] not in gone
                   and cleanup.cached(media.file(c["media"]), cleanup.recipe_of(c)) is None]
    out += [{"kind": "pending-take", "item": i, "message": f"The clip on {_called(data, t)} needs a cleaned take that is not made yet; until it is, "
             "the original plays", "fix": clean_clips.HINT}
            for i, t in waiting]
    yield
    timed = [i for t in data.get("tracks", []) for k in ("notes", "hits") for i in t.get(k, [])]
    for n in range(0, len(timed), STEP):             # each item's times worked out and kept (item_times): the checks
        for i in timed[n:n + STEP]:                  # below then read them, all in one short step
            item_times.span(data, i)
        yield
    with past_end.same_song():                       # the song's warnings read once, then named by the check that said each
        warnings, ties, late, held = (doc.kind.warnings(data), past_end.ties(data), past_end.late(data),
                                      past_end.held(data))
    for w in warnings:
        kind = "broken-tie" if w in ties else "after-the-end" if w in late else "held-past-end" if w in held else "no-longer-made"
        many = kind in ("after-the-end", "held-past-end")          # one line naming several: no one item to select
        out.append({"kind": kind, "item": w.split(":", 1)[0] if ":" in w and not many else "", "message": w, "fix": FIXES[kind]})
    if cut := past_end.hard_end(data):
        out.append({"kind": "hard-end", "item": cut, "message": "Soft end is off and sound is still playing at the song's Length, "
                    "so the file ends with a click", "fix": "Turn Soft end back on (doc.set endFade true), or end the music before the Length"})
    if engine is not None:                           # notes a track's recorded sound can't play (the render would refuse)
        out += [{**p, "fix": FIXES["out-of-range"]} for p in note_ranges.problems(data, engine)]


def _files(folder, refs) -> list[dict]:
    """The shared file rule's rows (rostrum_core.project.media_problems), in its order. Whether a file is there is asked
    every time (a file put back shows at once); whether a file that is there lies outside the song's folder (two path
    resolves, ~0.6 ms a clip) is the same for the same folder and path, so the rule's answer for it is kept."""
    missing: dict = {}
    for r in P.media_problems(folder, refs, outside=False):
        missing.setdefault(r["item"], []).append(r)
    out = []
    for ref in refs:
        rows = missing.pop(ref[0], [])
        if not rows:
            key = (str(folder), *ref)
            if key not in _OUTSIDE:
                if len(_OUTSIDE) > 10_000:
                    _OUTSIDE.clear()
                _OUTSIDE[key] = [r for r in P.media_problems(folder, [ref]) if r["kind"] == "outside-project"]
            rows = _OUTSIDE[key]
        out += [dict(r) for r in rows]
    return out
