"""Go back (or forward) to a point in the song's history: the song as it stood right after step `seq`, reached by taking
back the steps made since and bringing back the ones taken back since, never by rewriting anything. Nothing is lost:
the steps after it stay in History, taken back, and going to a later row brings them back.

Built on the core's undo_changes / redo_changes (each refused in words when a later change on the same things stands in
the way, history.blockers). Going only back, or only forward, is one step; a point with both is two (back, then forward).
(Generic: a candidate for rostrum_core's doc_undo, kept here until the shared core takes it.)
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes


def plan(doc, seq: int) -> tuple[list, list]:
    """(take back, bring back): the originals that stand otherwise now than right after step `seq`."""
    h = doc.history
    if not 0 <= seq <= doc.seq:
        raise RostrumError(codes.BAD_ARGUMENT, "go to", f"step {seq}", f"is not a step of this song (0 to {doc.seq})")
    back, forth = [], []
    for c in h.changes:
        if not c.original:
            continue
        then = c.seq <= seq and h.done_before(c.seq, seq + 1)
        if h.done[c.seq] and not then:
            back.append(c)
        elif not h.done[c.seq] and then:
            forth.append(c)
    return back, forth


def go_to(doc, seq: int, who, label: str = "") -> list:
    """Make the song stand as right after step `seq`. Returns the new steps ([] when it already does)."""
    back, forth = plan(doc, seq)
    words = label or (doc.history.get(seq).label if seq else "the start")
    made = []
    if back:
        made.append(doc.undo_changes(back, who, f"Back to: {words}"))
    if forth:
        made.append(doc.redo_changes(forth, who, f"Forward to: {words}"))
    return made
