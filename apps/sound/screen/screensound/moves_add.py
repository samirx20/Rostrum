"""Adding a note or a drum hit as operation calls (no Qt): the grid cell a click lands in, written in the form the track's
items already use (seconds or beats), a chord on the new note when Draw has one chosen (moves.py has the rest)."""
from __future__ import annotations

from rostrum_sound.doc import ids as note_ids

from . import key_lock, timing


def add_hit_call(doc, track_id, t: float, drum: str, free: bool = False, grid=None, px: float = 0.0) -> dict:
    """A drum hit on `drum` in the grid cell at `t` (`px`: one screen pixel in seconds, timing.snap), written in the form the track's hits already use (beats by default)."""
    root, track = doc.data, doc.item(track_id)
    first = next(iter(track.get("hits", [])), None)
    at = timing.snap(t, root, free, grid, "cell", px)
    when = round(at, 4) if first is not None and isinstance(first["at"], (int, float)) else         {"beat": round(timing.beat(at, root), 4)}
    return {"op": "hit.add", "target": [track_id], "args": {"drum": drum, "at": when}}


def add_note_call(doc, track_id, t: float, key: int, free: bool = False, beats: float = 1.0, grid=None,
                  px: float = 0.0, lock: bool = False) -> dict:
    """A note `beats` long on `key` in the grid cell at `t` (`px`: one screen pixel in seconds, timing.snap), written in the form the track's
    notes already use (beats by default)."""
    root, track = doc.data, doc.item(track_id)
    first = next(iter(track.get("notes", [])), None)
    secs = first is not None and isinstance(first["at"], (int, float))
    at = timing.snap(t, root, free, grid, "cell", px)
    key = key_lock.snapped(root, at, key) if lock and not free else key       # Keep notes in the key
    pitch = key if first is not None and isinstance(first["pitch"], int) else timing.name(key)
    if secs:
        args = {"at": round(at, 4), "dur": round(timing.spb(root, at) * beats, 4)}
    else:
        args = {"at": {"beat": round(timing.beat(at, root), 4)}, "dur": {"beats": beats}}
    return {"op": "note.add", "target": [track_id], "args": {"pitch": pitch, **args}}


class _Taken:
    """The document's ids, asked one at a time (no walk of the whole song for one click)."""

    def __init__(self, doc):
        self.doc = doc

    def __contains__(self, item_id):
        return self.doc.has(item_id)


def add_note_calls(doc, track_id, t: float, key: int, chord: str = "", **kw) -> list[dict]:
    """What a Draw click applies: the note (`add_note_call`) and, with a chord chosen in Note ▾ › Draw (`chord`: "key",
    "major", "minor", "power"), a `note.chord` on it that adds the other tones: one apply, so one undo step. The
    note gets its own id first so the chord call can name it."""
    call = add_note_call(doc, track_id, t, key, **kw)
    if not chord:
        return [call]
    nid = note_ids.note(track_id, call["args"]["at"], doc.data, _Taken(doc))      # the id note.add would give it
    call["args"]["id"] = nid
    return [call, {"op": "note.chord", "target": [nid], "args": {"shape": chord}}]
