"""One history per document (OPERATIONS.md § 6): changes only ever get added. Undo and redo are new changes
that re-toggle an earlier one, per author. This module keeps the list and answers questions about it;
`Document` makes the changes.

An *original* change is anything that isn't an undo or a redo. Each original is either done or undone; `at`
is the step that last did or undid it. Undo picks the author's latest done original; redo the latest one they
undid, as long as they haven't made a new change since.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .storage import doc_hash

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
    _hash: str = ""                                # hash_after: the document's hash after this change
    undoes: list = field(default_factory=list)     # seqs of originals this step undid
    redoes: list = field(default_factory=list)     # seqs of originals this step re-did
    t: float = 0.0                                 # clock time: merging nudges, ordering undo across documents
    step: str | None = None                        # one step across documents (joint.py): undone / redone together

    _after: dict | None = field(default=None, repr=False, compare=False)

    @property
    def hash_after(self) -> str:
        """Worked out from the document after this change on first read (saving, comparing): hashing a big
        document on every change was most of a change's time."""
        if self._after is not None:
            self._hash, self._after = doc_hash(self._after), None
        return self._hash

    @hash_after.setter
    def hash_after(self, value: str):
        self._hash, self._after = value, None

    def hash_of(self, data: dict):
        """hash_after will be data's hash; data must not change in place afterwards (edits.fork)."""
        self._hash, self._after = "", data

    def ident(self) -> tuple:
        """The same step, as read back from a file (the seq alone isn't: another program's step can have it)."""
        return self.seq, self.t, self.step, self.label

    @property
    def original(self) -> bool:
        return not self.undoes and not self.redoes

    def to_dict(self) -> dict:
        return {"seq": self.seq, "based_on": self.based_on, "who": self.who.to_dict(), "label": self.label,
                "when": self.when, "session": self.session, "calls": self.calls,
                "edits": [E.to_dict(e) for e in self.edits], "hash_after": self._hash,   # "" until known (storage)
                "undoes": self.undoes, "redoes": self.redoes, "t": self.t,
                **({"step": self.step} if self.step else {})}

    @classmethod
    def from_dict(cls, d) -> "Change":
        return cls(d["seq"], d["based_on"], Who.from_dict(d["who"]), d["label"], d["when"],
                   [E.from_dict(e) for e in d["edits"]], d.get("calls", []), d.get("session"),
                   d.get("hash_after", ""), d.get("undoes", []), d.get("redoes", []), d.get("t", 0.0),
                   d.get("step"))


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

    def mark(self) -> tuple[int, dict]:
        """Where the history stands now (the newest step, which originals are done), for `moved_since`."""
        return self.seq, dict(self.done)

    def moved_since(self, mark) -> int:
        """How many originals are not as they were at `mark`: made since and still done, or older ones undone or
        redone since. 0 right after `mark`; Undo takes it down, Redo brings it back (a screen's "N changes")."""
        seq0, done0 = mark
        return sum(1 for c in self.changes if c.original
                   and (self.done[c.seq] if c.seq > seq0 else self.done[c.seq] != done0.get(c.seq)))

    def add(self, c: Change):
        self.changes.append(c)
        if c.original:
            self.done[c.seq], self.at[c.seq] = True, c.seq
        for s in c.undoes:
            self.done[s], self.at[s] = False, c.seq
        for s in c.redoes:
            self.done[s], self.at[s] = True, c.seq

    def acted(self, c: Change) -> float:
        """Clock time of the step that last did or undid original `c` (desk.py orders undo across documents by it)."""
        return self.get(self.at[c.seq]).t

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
                                       f"can't be taken back or brought back: {c.who.words()} changed {k} since "
                                       f"(\"{c.label}\", step {c.seq})", hint="Undo that first, in History.")

    def who_changed(self, id_, field_=None) -> Change | None:
        want = (id_,) if field_ is None else (id_, field_)
        for c in reversed(self.changes):
            if E.overlap(self.keys(c), {want}):
                return c
        return None

    def since(self, seq) -> list[Change]:
        return [c for c in self.changes if c.seq > seq]
