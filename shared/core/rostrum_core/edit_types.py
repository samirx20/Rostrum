"""The six edit kinds (see edits.py) as plain data: what each carries, how a history line holds it, how it reverses."""
from __future__ import annotations

from dataclasses import dataclass, field, fields


MISSING = "<missing>"     # a Set whose value is MISSING removes the field; before=MISSING: it wasn't there
NO_AFTER = "<index>"      # place by index, not after a sibling


@dataclass
class Set:
    id: str
    path: list
    value: object = MISSING
    before: object = MISSING


@dataclass
class Insert:
    id: str
    parent: str
    key: str
    index: int
    item: dict = field(default_factory=dict)
    after: object = NO_AFTER          # sibling id, None = first, NO_AFTER = use index


@dataclass
class Remove:
    id: str
    parent: str = ""
    key: str = ""
    index: int = 0
    item: dict = field(default_factory=dict)
    after: object = NO_AFTER          # filled on apply: the sibling it followed (for the reverse)


@dataclass
class Move:
    id: str
    from_: tuple = ()                 # (parent, key, index)
    to: tuple = ()
    after: object = NO_AFTER
    from_after: object = NO_AFTER     # filled on apply


@dataclass
class Shift:
    """The number at `path` of every item in `ids` moved by the same amount `by`: each becomes round(value + by,
    places) (`places` None: not rounded). Exact both ways: `to` gives some items an exact value instead (an undo's), and
    applying fills `back` with the old values that the sum taken back would not give exactly (rounding), so its
    reverse restores every value as it was, type included."""
    ids: list
    path: list
    by: object = 0
    places: object = None
    to: dict = field(default_factory=dict)
    back: dict = field(default_factory=dict)


@dataclass
class Many:
    """Many items brought in (only Inserts) or taken out (only Removes) as one edit: the same as its edits one by one,
    in order, but each list rebuilt once (edit_many.py). One history entry; its reverse is theirs in reverse order. A
    reader that looks at items one by one reads `flat(edits)`."""
    edits: list


KINDS = {"set": Set, "insert": Insert, "remove": Remove, "move": Move, "shift": Shift, "many": Many}


_NAMES = {c: k for k, c in KINDS.items()}
_FIELDS = {c: [f.name for f in fields(c)] for c in KINDS.values()}


def to_dict(e) -> dict:
    """The edit as its history line holds it. Its values are shared, not copied (dataclasses.asdict deep-copied every
    item a big Ctrl+D brought in, only to write it out): the caller writes it and drops it."""
    if type(e) is Many:
        return {"edit": "many", "edits": [to_dict(x) for x in e.edits]}
    out = {"edit": _NAMES[type(e)]}
    for name in _FIELDS[type(e)]:
        v = getattr(e, name)
        out[name] = list(v) if isinstance(v, tuple) else v
    return out


def from_dict(d) -> object:
    d = dict(d)
    cls = KINDS[d.pop("edit")]
    if cls is Many:
        return Many([from_dict(x) for x in d["edits"]])
    if cls is Move:
        d["from_"], d["to"] = tuple(d["from_"]), tuple(d["to"])
    return cls(**d)


def ids(e) -> list:
    """The items an edit addresses (a Shift, a Many: many; the others: one)."""
    if isinstance(e, Many):
        return [x.id for x in e.edits]
    return e.ids if isinstance(e, Shift) else [e.id]


def flat(edits):
    """The edits one by one, a Many's own in its place (Inserts and Removes as their one-by-one apply records them)."""
    for e in edits:
        if type(e) is Many:
            yield from e.edits
        else:
            yield e


def reverse(e):
    """The edit that undoes an applied edit."""
    if isinstance(e, Set):
        return Set(e.id, list(e.path), e.before, e.value)
    if isinstance(e, Insert):
        return Remove(e.id, e.parent, e.key, e.index, e.item)
    if isinstance(e, Remove):
        return Insert(e.id, e.parent, e.key, e.index, e.item, e.after)
    if isinstance(e, Move):
        return Move(e.id, e.to, e.from_, e.from_after)
    if isinstance(e, Shift):
        return Shift(list(e.ids), list(e.path), -e.by, e.places, dict(e.back))
    if isinstance(e, Many):
        return Many([reverse(x) for x in reversed(e.edits)])
    raise TypeError(f"not an edit: {e!r}")
