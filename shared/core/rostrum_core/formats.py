"""Which file format a document's data is in, step by step through its history.

A format step (DocKind.migrations) runs once per document: on open, the steps from the format the data is in up to
the app's own are recorded as one change by Rostrum (who.UPGRADE) that carries `format` = [from, to]. The document
file's "version" is the format of the data at its step "at"; the history steps after it may carry the data further,
so the format the opened data is in is the last `format` among the steps played on top of the file (`after`), never
the file's number alone (a song folded before its upgrade step was moved again on every open: 2026-10-26).

Steps written before they carried `format` are read by their label (DocKind.upgraded). An upgrade step that ran on
data already past its `from` (`reruns`) was that bug: opening takes its edits back (`repair`).
"""
from __future__ import annotations

from . import edits as E
from .who import UPGRADE


def fill(changes, kind) -> None:
    """Older upgrade steps without `format` get it from their label (kind.upgraded), in place."""
    if kind.upgraded is None:
        return
    for c in changes:
        if c.format is None and c.who == UPGRADE:
            got = kind.upgraded(c.label)
            c.format = list(got) if got else None


def after(version: int, changes) -> int:
    """The format of data at `version` once `changes` are played on it."""
    for c in changes:
        if c.format:
            version = c.format[1]
    return version


def before(changes, seq: int) -> int | None:
    """The format of the data at step `seq` when a later step brought it up to date (its `from`), else None."""
    return next((c.format[0] for c in changes[seq:] if c.format), None)


def reruns(changes) -> list:
    """Upgrade steps that ran on data already past their `from` (the format they started from), oldest first."""
    out, at = [], None
    for c in changes:
        if c.format:
            if c.who == UPGRADE and at is not None and c.format[0] < at:
                out.append(c)
            at = c.format[1]
    return out


def repair(doc) -> str | None:
    """Take back the edits of upgrade steps that ran twice (`reruns`) as one change by Rostrum. When something made
    since touches the same things (an agent already put it right by hand), they are left as they are and a step by
    Rostrum with `format` [n, n] says so, once. A plain sentence saying what was done (never silent), None when there
    was nothing to repair."""
    ch = doc.history.changes
    settled = max((c.seq for c in ch if c.who == UPGRADE and c.format and c.format[0] == c.format[1]), default=0)
    bad = [c for c in reruns(ch) if c.seq > settled and c.edits and doc.history.done.get(c.seq)]
    if not bad:
        return None
    from .errors import RostrumError
    n = f"{len(bad)} repeated file-format step{'s' * (len(bad) != 1)}"
    try:
        doc.history.blockers(bad)
    except RostrumError as e:
        label = f"Checked: {n} left as they are: later steps changed the same things ({e.problem})"
        doc.commit(doc.data, [], UPGRADE, label, format=[after(0, ch)] * 2)
        return label + ". Check it by ear."
    rev = [E.reverse(e) for c in sorted(bad, key=lambda c: -c.seq) for e in reversed(c.edits)]
    label = f"Repaired: {n} taken back"
    doc._replay(rev, UPGRADE, label, undoes=[c.seq for c in bad])
    return label
