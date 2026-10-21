"""One history per person across the documents they edit together (AGENTS.md rule 3): a 2D document and the
project's shared markers, say. Undo takes back the person's newest change in any of them; redo brings back the one
they undid last, as long as they haven't made a new change anywhere since.

Each document still records its own changes and still refuses an undo that a later change by someone else depends
on (history.py); this module only picks which document's step comes next, by clock time (Change.t, saved).
A tie (old histories saved without a time) goes to the first document given: the one on screen.
"""
from __future__ import annotations

from .history import Change
from .who import Who


def _newest(docs, pick, who):
    best = None
    for d in docs:
        c = pick(d.history, who)
        if c is not None and (best is None or d.history.acted(c) > best[0]):
            best = (d.history.acted(c), d)
    return best


def undo(docs, who: Who):
    """(document, the undo change) for the person's newest live change across `docs`; None when there is none."""
    best = _newest(docs, lambda h, w: h.last_undoable(w), who)
    return (best[1], best[1].undo(who)) if best else None


def redo(docs, who: Who):
    """(document, the redo change) for what the person undid last across `docs`; None when there is nothing to
    redo, or the person has made a new change in any of them since that undo."""
    best = _newest(docs, lambda h, w: h.last_redoable(w), who)
    newest_own = max((c.t for d in docs for c in d.history.changes if c.original and c.who == who), default=0.0)
    if best is None or best[0] < newest_own:
        return None
    return best[1], best[1].redo(who)


def changes(docs) -> list[tuple[object, Change]]:
    """Every change of every document, oldest first: (document, change). The one "who changed what" list."""
    rows = [(d, c) for d in docs for c in d.history.changes]
    return sorted(rows, key=lambda r: r[1].t)
