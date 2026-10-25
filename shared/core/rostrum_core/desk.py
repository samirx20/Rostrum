"""One history per person across the documents they edit together (AGENTS.md rule 3): a 2D document and the
project's shared markers, say. Undo takes back the person's newest change in any of them; redo brings back the one
they undid last, as long as they haven't made a new change anywhere since.

Each document still records its own changes and still refuses an undo that a later change by someone else depends
on (history.py); this module only picks which document's step comes next, by clock time (Change.t, saved).
A tie (old histories saved without a time) goes to the first document given: the one on screen.

A step that reached several documents (joint.py: 2D's "Add a sound here" writes Sound's song and a marker) is taken
back or brought back whole: every document is checked first, then each is changed, newest first for undo and oldest
first for redo; a refusal in any of them changes none. A document the step reached that isn't in `docs` is asked
for with `open_item(item_id)` (the app opens it); without it the undo is refused in words, never done by half.
"""
from __future__ import annotations

from . import joint
from .errors import RostrumError, codes
from .history import Change
from .who import Who


class Hit(tuple):
    """(document, change) of the step's newest change, as before; `.all`: every (document, change) the step made."""
    all: list


def _hit(pairs):
    h = Hit(pairs[-1])
    h.all = pairs
    return h


def _newest(docs, pick, who):
    for d in docs:                              # pick from what every program saved, not an old picture
        if d.live is not None:
            d.live.catch_up()
    best = None
    for d in docs:
        c = pick(d.history, who)
        if c is not None and (best is None or d.history.acted(c) > best[0]):
            best = (d.history.acted(c), d, c)
    return best


def _partners(docs, first, c, who, done: bool, open_item):
    """Every (document, [originals]) of `c`'s step by `who` that are done (undo) / undone (redo), opening documents
    the step reached that aren't here."""
    docs = list(docs)
    have = {d.item_id for d in docs}
    for item in joint.items(first.folder, c.step):
        if item in have:
            continue
        d = open_item(item) if open_item is not None else None
        if d is None:
            raise RostrumError(codes.CONFLICT, "undo", f'"{c.label}"', f'also changed "{item}", which is not open here',
                               hint="Open it, or take the step back in History, document by document.")
        if d.live is not None:
            d.live.catch_up()
        docs.append(d)
    out = []
    for d in docs:
        cs = [x for x in d.history.of_step(c.step) if x.original and x.who == who and d.history.done[x.seq] == done]
        if cs:
            out.append((d, cs))
    return out


def _whole(parts, act, newest_first: bool):
    for d, cs in parts:                         # refuse before changing anything
        d.history.blockers(cs, max(d.history.at[x.seq] for x in cs))
    parts = sorted(parts, key=lambda p: max(x.t for x in p[1]), reverse=newest_first)
    with joint.replay(), joint.step():
        return [(d, act(d, cs)) for d, cs in parts]


def undo(docs, who: Who, open_item=None):
    """(document, the undo change) for the person's newest live change across `docs`; None when there is none.
    A step across documents is undone whole (`.all` on the result)."""
    best = _newest(docs, lambda h, w: h.last_undoable(w), who)
    if best is None:
        return None
    _, d, c = best
    parts = _partners(docs, d, c, who, True, open_item) if c.step else [(d, [c])]
    return _hit(_whole(parts, lambda d, cs: d.undo_changes(cs, who, f"Undid: {c.label}"), True))


def redo(docs, who: Who, open_item=None):
    """(document, the redo change) for what the person undid last across `docs`; None when there is nothing to
    redo, or the person has made a new change in any of them since that undo. A step is redone whole."""
    best = _newest(docs, lambda h, w: h.last_redoable(w), who)
    newest_own = max((c.t for d in docs for c in [d.history.newest_own(who)] if c is not None), default=0.0)
    if best is None or best[0] < newest_own:
        return None
    _, d, c = best
    parts = _partners(docs, d, c, who, False, open_item) if c.step else [(d, [c])]
    return _hit(_whole(parts, lambda d, cs: d.redo_changes(cs, who, f"Redid: {c.label}"), False))


def changes(docs) -> list[tuple[object, Change]]:
    """Every change of every document, oldest first: (document, change). The one "who changed what" list."""
    rows = [(d, c) for d in docs for c in d.history.changes]
    return sorted(rows, key=lambda r: r[1].t)
