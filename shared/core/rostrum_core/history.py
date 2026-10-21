"""One history per document (OPERATIONS.md § 6): changes only ever get added. Undo and redo are new changes
that re-toggle an earlier one, per author. This module keeps the list and answers questions about it;
`Document` makes the changes.

An *original* change is anything that isn't an undo or a redo. Each original is either done or undone; `at`
is the step that last did or undid it. Undo picks the author's latest done original; redo the latest one they
undid, as long as they haven't made a new change since.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import edits as E
from .errors import RostrumError, codes
from .who import Who


@dataclass
class Change:
    seq: int
    based_on: int
    who: Who
    label: str
    when: str
    edits: list
    calls: list = field(default_factory=list)
    session: str | None = None
    hash_after: str = ""
    undoes: list = field(default_factory=list)     # seqs of originals this step undid
    redoes: list = field(default_factory=list)     # seqs of originals this step re-did
    t: float = 0.0                                 # clock time, for merging nudges (not saved)

    @property
    def original(self) -> bool:
        return not self.undoes and not self.redoes

    def to_dict(self) -> dict:
        return {"seq": self.seq, "based_on": self.based_on, "who": self.who.to_dict(), "label": self.label,
                "when": self.when, "session": self.session, "calls": self.calls,
                "edits": [E.to_dict(e) for e in self.edits], "hash_after": self.hash_after,
                "undoes": self.undoes, "redoes": self.redoes}

    @classmethod
    def from_dict(cls, d) -> "Change":
        return cls(d["seq"], d["based_on"], Who.from_dict(d["who"]), d["label"], d["when"],
                   [E.from_dict(e) for e in d["edits"]], d.get("calls", []), d.get("session"),
                   d.get("hash_after", ""), d.get("undoes", []), d.get("redoes", []))


class History:
    def __init__(self, lists: dict):
        self.lists = lists
        self.changes: list[Change] = []
        self.done: dict[int, bool] = {}
        self.at: dict[int, int] = {}
        self.versions: dict[str, int] = {}

    @property
    def seq(self) -> int:
        return self.changes[-1].seq if self.changes else 0

    def add(self, c: Change):
        self.changes.append(c)
        if c.original:
            self.done[c.seq], self.at[c.seq] = True, c.seq
        for s in c.undoes:
            self.done[s], self.at[s] = False, c.seq
        for s in c.redoes:
            self.done[s], self.at[s] = True, c.seq

    def get(self, seq) -> Change:
        return self.changes[seq - 1]

    def keys(self, c: Change) -> set:
        return set().union(*(E.keys(e, self.lists) for e in c.edits)) if c.edits else set()

    def last_undoable(self, who: Who) -> Change | None:
        mine = [c for c in self.changes if c.original and c.who == who and self.done[c.seq]]
        return max(mine, key=lambda c: self.at[c.seq], default=None)

    def last_redoable(self, who: Who) -> Change | None:
        newest_own = max((c.seq for c in self.changes if c.original and c.who == who), default=0)
        mine = [c for c in self.changes if c.original and c.who == who and not self.done[c.seq]
                and self.at[c.seq] > newest_own]
        return max(mine, key=lambda c: self.at[c.seq], default=None)

    def blockers(self, targets: list[Change], since: int):
        """Refuse to toggle `targets` when a later live change touched the same things."""
        mine = {c.seq for c in targets}
        touched = set().union(*(self.keys(c) for c in targets))
        for c in self.changes:
            if c.original and c.seq not in mine and self.done[c.seq] and self.at[c.seq] > since:
                hit = E.overlap(self.keys(c), touched)
                if hit:
                    k = E.key_text(sorted(hit)[0])
                    raise RostrumError(codes.CONFLICT, "undo", f'"{targets[-1].label}"',
                                       f"can't be undone or redone: change {c.seq} ({c.who}, \"{c.label}\") "
                                       f"changed {k} after it", hint="Undo that change first.")

    def who_changed(self, id_, field_=None) -> Change | None:
        want = (id_,) if field_ is None else (id_, field_)
        for c in reversed(self.changes):
            if E.overlap(self.keys(c), {want}):
                return c
        return None

    def since(self, seq) -> list[Change]:
        return [c for c in self.changes if c.seq > seq]
