"""Many notes or hits selected: the settings panel's merged rows without evaluating every item (no Qt).

Ctrl+A on a 1,440-note track evaluated 1,440 row lists (rows.evaluate, inspect.musical_rows) to merge them: ~0.5 s
on every pick, duplicate or nudge. Notes alike in everything but their values have the same rows but for `value`:
which rows apply, their kind, holds and valid come from the same facts and the same structural fields. So the
items are grouped by those (`_key`), each group's first item is evaluated in full, and of every other item only the
values are read, through inspect.musical_row (the one place a value is shown), and only until a row is known to
differ. many.merge then folds the groups' rows with those differing rows marked (`differs`): the result is exactly
many.merge of every item's own rows (guarded by tests/test_select.py).

A value is "plain" (read per item) when nothing but the row's own value depends on it: no valid_when names it (each
kind's own rule, many.own_rules, for mixed kinds), it has no "shown while changed" rule, and it is no pick or list.
Every other field is in the group key, with the type each plain value is written in. Only notes and hits are grouped
(the kinds that come by the thousand); any other item in the selection is evaluated as before. Not folded: panels
with folds (sections), and a bridge whose key marks, expressions or starting values differ per item.
"""
from __future__ import annotations

from rostrum_core.conditions import refs
from rostrum_gui import DocBridge, many

from . import inspect

FOLDED = ("note", "hit")
_NONE = object()                            # a field not written at all (its row shows the default)
LEAST = 8                                   # fewer items: each evaluated, as for one
PER_ITEM = ("anim_state", "expr_state", "starts")      # hooks that would make rows differ per item (choices: _plain)


def merged(bridge, items: list[dict], root: dict) -> list[dict] | None:
    """The merged rows of `items` (the bridge's panel state), or None when they are not ones to fold."""
    k = bridge._kit
    if len(items) < LEAST or any(getattr(type(bridge), h) is not getattr(DocBridge, h) for h in PER_ITEM):
        return None
    reg = bridge.doc.kind.registry
    rules = [r["valid_when"] for r in k.static if r["row"] == "param"]
    rules += [p.valid_when for t in {it["type"] for it in items} & set(FOLDED) for p in reg.field_op(t).params]
    named = {n for c in rules for kind, n in refs(c) if kind == "param"}      # (each kind's own rules: mixed kinds)
    plain = _plain(k.static, named)
    if plain is None:
        return None
    struct = sorted({r["id"] for r in k.static if r["row"] == "param"} - plain | named)
    plain = sorted(plain)
    groups: dict = {}             # key -> ({plain row id: the first item's evaluated row}, its finished rows)
    first, todo, differs, lengths = None, [], set(), set()
    for n, it in enumerate(items):
        key = _key(bridge, it, struct, plain) if it["type"] in FOLDED else n
        g = groups.get(key)
        if g is None:
            rows = bridge._item_rows(it)
            ev = {r["id"]: r for r in rows if r["row"] == "param" and r["id"] in plain}
            g = groups[key] = (ev, inspect.musical_rows(it, rows, root))
            if first is None:                   # the first item: what every other value is compared with
                first = {r["id"]: (it.get(r["id"], _NONE), r["value"]) for r in g[1] if r["id"] in ev}
                todo, kind = list(first), it["type"]
                lengths = {i for i in todo if inspect.time_kind(it, i) == "length"}
            continue                            # (a group's own first item: many.merge compares it)
        for i in [i for i in todo if i in g[0]]:
            raw, was = it.get(i, _NONE), first[i]
            if type(raw) is type(was[0]) and raw == was[0] and it["type"] == kind and i not in lengths:
                continue                        # written as the first item's: shown as it (but a length)
            if _value(it, g[0][i], root) != was[1]:
                differs.add(i)
                todo.remove(i)
    return many.merge([g[1] for g in groups.values()], differs)


def _value(it: dict, r: dict, root: dict):
    """The item's value in row `r` as its own rows would show it (rows.evaluate, then inspect.musical_row). A value
    written as another item's is shown as that one's, but for a length: in beats it lasts as long as the tempo
    where it starts says (the caller skips the rest)."""
    i = r["id"]
    v = inspect.shown_field(it, i, root)
    return inspect.musical_row(it, {i: v}, {**r, "value": r["default"] if v is None and i not in it else v}, root)["value"]


def _plain(static: list[dict], named: set) -> set | None:
    """The params whose value only ever shows as their own row's value (None: a layout that can't be folded).
    `named`: the fields any valid_when reads."""
    if any(r["row"] == "folds" or "fold" in r or "switch" in r for r in static):
        return None
    params = [r for r in static if r["row"] == "param"]
    if any(r["type"] == "list" or r.get("control") == "pick" for r in params):
        return None                             # (their choices may depend on where each item is)
    return {r["id"] for r in params if r["id"] not in named and r.get("shown", "") != "changed" and r["id"] != "ridePath"}


def _key(bridge, it: dict, struct: list, plain: list) -> tuple:
    """What the item's rows are made of but for their values: its facts, what its page shows elsewhere, its fields
    that decide which rows apply, and the type each plain value is written in (a time written in beats is shown as
    bars.beats). Written values, not shown ones: the same written value is always shown the same (but a length)."""
    facts = bridge.facts_of(it)
    return (it["type"], tuple(sorted(facts.items())), frozenset(bridge.on_page(it)),
            tuple(_frozen(it.get(n)) for n in struct), tuple(type(it.get(n)) for n in plain))


def _frozen(v):
    try:
        hash(v)
        return type(v), v
    except TypeError:
        return type(v), repr(v)
