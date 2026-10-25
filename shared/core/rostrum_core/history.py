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
        self._asked: dict = {}                      # (question, who) -> answer, until the next step (add)
        self._tallies: dict = {}                    # id(mark) -> [mark, steps counted, count, {seq: done}]
        self._steps: dict = {}                      # step id (joint.py) -> its changes here

    @property
    def seq(self) -> int:
        return self.changes[-1].seq if self.changes else 0

    def mark(self) -> tuple[int, dict]:
        """Where the history stands now (the newest step, which originals are done), for `moved_since`."""
        return self.seq, dict(self.done)

    def moved_since(self, mark) -> int:
        """How many originals are not as they were at `mark`: made since and still done, or older ones undone or
        redone since. 0 right after `mark`; Undo takes it down, Redo brings it back (a screen's "N changes").
        Kept as a tally per mark that takes in only the steps added since it was last asked (a screen asks on every
        change: a count over the whole history grew with it)."""
        seq0, done0 = mark
        t = self._tallies.get(id(mark))
        if t is None or t[0] is not mark:
            t = self._tallies[id(mark)] = [mark, 0, 0, {}]

        def counts(s, v):                           # does original s, done or not (None: not made yet), count?
            return 0 if v is None else int(v if s > seq0 else v != done0.get(s))
        for c in self.changes[t[1]:]:
            for s, v in ([(c.seq, True)] if c.original else []) + [(s, False) for s in c.undoes] +                     [(s, True) for s in c.redoes]:
                t[2] += counts(s, v) - counts(s, t[3].get(s, done0.get(s) if s <= seq0 else None))
                t[3][s] = v
        t[1] = len(self.changes)
        return t[2]

    def add(self, c: Change):
        self.changes.append(c)
        self._asked.clear()
        if c.step:
            self._steps.setdefault(c.step, []).append(c)
        if c.original:
            self.done[c.seq], self.at[c.seq] = True, c.seq
        for s in c.undoes:
            self.done[s], self.at[s] = False, c.seq
        for s in c.redoes:
            self.done[s], self.at[s] = True, c.seq

    def acted(self, c: Change) -> float:
        """Clock time of the step that last did or undid original `c` (desk.py orders undo across documents by it)."""
        return self.get(self.at[c.seq]).t

    def of_step(self, step) -> list[Change]:
        """The changes here that are part of one step across documents (joint.py), oldest first."""
        return list(self._steps.get(step, ()))

    def get(self, seq) -> Change:
        return self.changes[seq - 1]

    def keys(self, c: Change) -> set:
        return set().union(*(E.keys(e, self.lists) for e in c.edits)) if c.edits else set()

    # Undo / redo picks: read from the newest step back, stopping at the answer, and kept until the next step (the
    # screen's labels ask on every change; a look over the whole history grew with it).
    def last_undoable(self, who: Who) -> Change | None:
        """`who`'s done original that was done last (the largest `at`): the newest step whose doing of it is still
        its last act."""
        return self._ask("undo", who, lambda: self._newest_act(who, True, lambda c: [c.seq] if c.original else c.redoes))

    def last_redoable(self, who: Who) -> Change | None:
        """`who`'s original undone last, as long as they made no new original since."""
        own = self.newest_own(who)
        return self._ask("redo", who, lambda: self._newest_act(who, False, lambda c: c.undoes, own.seq if own else 0))

    def newest_own(self, who: Who) -> Change | None:
        """`who`'s newest original step."""
        return self._ask("own", who, lambda: next((c for c in reversed(self.changes) if c.original and c.who == who), None))

    def _ask(self, q, who, work):
        key = (q, who)
        if key not in self._asked:
            self._asked[key] = work()
        return self._asked[key]

    def _newest_act(self, who, done, acted, after=0):
        for c in reversed(self.changes):
            if c.seq <= after:
                break
            hit = [s for s in acted(c) if self.at.get(s) == c.seq and self.done[s] is done and self.get(s).who == who]
            if hit:
                return self.get(min(hit))           # one step that acted on several: the oldest, as before
        return None

    def blockers(self, targets: list[Change], since: int):
        """Refuse to toggle `targets` when a later live change touched the same things. Only originals acted on
        after step `since` can (their `at` is later): read from the steps after it, not the whole history."""
        mine = {c.seq for c in targets}
        touched = set().union(*(self.keys(c) for c in targets))
        later = {s for x in self.changes[since:] for s in ([x.seq] if x.original else [*x.undoes, *x.redoes])}
        for c in (self.get(s) for s in sorted(later)):
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
