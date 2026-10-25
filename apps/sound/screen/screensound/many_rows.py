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
    for n, (it, key) in enumerate(zip(items, _keys(bridge, items, struct, plain))):
        g = groups.get(key)
        if g is None:
            rows = bridge.sound_rows(it)
            ev = {r["id"]: r for r in rows if r["row"] == "param" and r["id"] in plain}
            g = groups[key] = (ev, inspect.musical_rows(it, rows, root))
            if first is None:                   # the first item: what every other value is compared with
                first = {r["id"]: (it.get(r["id"], _NONE), r["value"]) for r in g[1] if r["id"] in ev}
                todo, kind = list(first), it["type"]
                lengths = {i for i in todo if inspect.by_length(it, i)}
            continue                            # (a group's own first item: many.merge compares it)
        if not todo:                            # every plain row already known to differ: nothing left to read
            continue
        for i in [i for i in todo if i in g[0]]:
            raw, was = it.get(i, _NONE), first[i]
            if type(raw) is type(was[0]) and raw == was[0] and it["type"] == kind and i not in lengths:
                continue                        # written as the first item's: shown as it (but a length, or a bend)
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


_KEYS: dict = {}                            # item id -> (item, its parent, its page, its key): kept between merges
_LAYOUT: list = [None]                      # the layout those keys were made for (struct, plain)


def _keys(bridge, items: list[dict], struct: list, plain: list) -> list:
    """Each item's group key (`_key`; an item of another kind: its place, a group of its own). A key is kept while
    the item and its parent are the very same objects (a change writes new ones: rostrum_core/edits.py), its page
    shows the same and the layout is the same: a note's facts are its track's (doc/kind.py facts), so a tempo drag or
    a pick of the same notes again makes no key twice (6,600 a move, ~40 µs each, before)."""
    layout = (tuple(struct), tuple(plain))
    if _LAYOUT[0] != layout or len(_KEYS) > 100_000:
        _KEYS.clear()
        _LAYOUT[0] = layout
    idx, out, pages = bridge.doc.locs(), [], {}
    for n, it in enumerate(items):
        if it["type"] not in FOLDED:
            out.append(n)
            continue
        loc = idx.get(it["id"])
        parent = idx[loc.parent].item if loc is not None and loc.parent in idx else None
        page = pages.get(it["type"])        # a note's or a hit's page is its kind's (onpage.py; only a clip's is its own)
        if page is None:
            page = pages[it["type"]] = frozenset(bridge.on_page(it))
        kept = _KEYS.get(it["id"])
        if kept is None or kept[0] is not it or kept[1] is not parent or kept[2] != page:
            kept = _KEYS[it["id"]] = (it, parent, page, _key(bridge, it, struct, plain, page))
        out.append(kept[3])
    return out


def _key(bridge, it: dict, struct: list, plain: list, page: frozenset) -> tuple:
    """What the item's rows are made of but for their values: its facts, what its page shows elsewhere, its fields
    that decide which rows apply, and the type each plain value is written in (a time written in beats is shown as
    bars.beats). Written values, not shown ones: the same written value is always shown the same (but a length)."""
    facts = bridge.facts_of(it)
    return (it["type"], tuple(sorted(facts.items())), page,
            tuple(_frozen(it.get(n)) for n in struct), tuple(type(it.get(n)) for n in plain))


def _frozen(v):
    try:
        hash(v)
        return type(v), v
    except TypeError:
        return type(v), repr(v)
