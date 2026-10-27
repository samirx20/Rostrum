"""A step whose history line comes the frame after (live.py, in a window): the key's own frame pays only for the
change and this small note, `.rostrum/<item>.pending.json`, which says how to make the step again: the calls of an
apply, or which steps an undo / redo took back or brought back (never the edits: a whole-song Ctrl+D's line is
~1 MB of text, ~20-30 ms to write). The line itself is appended the frame after (Live.flush), while the history
file's lock is still held, so nobody else's step can come between.

A crash before that line is written leaves the note behind: opening the document (storage.open_doc) makes that step
again, through the same operations, on the document exactly as the note found it (the last step's identity must
match), and says so in `doc.notes`. A note that no longer matches (its line was written, or the file moved on) is
old and ignored; the next note overwrites it. While the history file's lock is held, the program that wrote the
note is alive and its line is on the way (an agent's server opening the song in that moment): nothing is made again.
"""
from __future__ import annotations

import json

from .userhome import held
from .who import Who


OWED: dict = {}         # history file -> the flush of a line this program still owes it (live.Live)


def settle(p):
    """Write the line this program still owes this history file, if any: opening or reading the file comes after it
    (reopening the song in the same window waited on its own lock)."""
    flush = OWED.get(str(p["history"]))
    if flush is not None:
        flush()


def path(p):
    return p["history"].with_name(p["history"].name.replace(".history.jsonl", ".pending.json"))


def intent(do, who, label, calls=(), seqs=(), session=None) -> dict:
    """What Document.apply / undo_changes / redo_changes leave for the door: how to make their step again."""
    return {"do": do, "who": who.to_dict(), "label": label, "calls": list(calls), "seqs": list(seqs), "session": session}


def note(p, after, what: dict):
    """Write the note: `after` the identity (Change.ident) of the last step the history file holds, None: none."""
    text = json.dumps({"after": list(after) if after else None, "intent": what}, ensure_ascii=False,
                      separators=(",", ":"))
    with open(path(p), "w", encoding="utf-8") as fh:     # (not atomic: a torn note can't be read and is ignored)
        fh.write(text)


def recover(doc, p) -> bool:
    """A note left by a crash, still matching the document as opened: make its step again. True when it did."""
    f = path(p)
    try:
        n = json.loads(f.read_text(encoding="utf-8"))
        after, what = n["after"], n["intent"]
    except (OSError, ValueError, KeyError, TypeError):
        return False
    ch = doc.history.changes
    if (list(ch[-1].ident()) if ch else None) != after or held(p["history"]):
        return False                                # (held: the window that wrote the note is alive, its line coming)
    who, label = Who.from_dict(what["who"]), what["label"]
    try:
        if what["do"] == "apply":
            made = doc.apply(what["calls"], who, label=label, session=what.get("session"), join=False)
        else:
            steps = [ch[s - 1] for s in what["seqs"]]
            made = (doc.undo_changes if what["do"] == "undo" else doc.redo_changes)(steps, who, label)
    except Exception as e:  # noqa: BLE001 — said, never silent: the file opens as its history left it
        doc.notes.append(f'The last step before Rostrum closed ("{label}") could not be made again: '
                         f"{type(e).__name__}: {e}")
        return False
    if made is not None:
        doc.notes.append(f'The last step before Rostrum closed ("{label}") was brought back.')
    return made is not None
