"""Many notes or hits selected: the settings panel's merged rows without evaluating every item (no Qt).

Ctrl+A on a 1,440-note track evaluated 1,440 row lists (rows.evaluate, inspect.musical_rows) to merge them: ~0.5 s
on every pick, duplicate or nudge. Notes alike in everything but their values have the same rows but for `value`:
which rows apply, their kind, holds and valid come from the same facts and the same structural fields. So the
items are grouped by those (`_key`), each group's first item is evaluated in full, and of every other item only the
values are read, through inspect.musical_row (the one place a value is shown), and only until a row is known to
differ. many.merge then folds the groups' rows with those differing rows marked (`differs`): the result is exactly
many.merge of every item's own rows (guarded by tests/test_select.py).

Each merge starts from the one before, but trusts nothing of it: keys are kept for notes changed only in plain values
(`_keys`), and the item last found to differ in a row is asked first (`_WITNESS`). A whole-song Right, its undo and
redo (3,607 notes and hits): 12-40 ms a merge before, 4-12 ms now (70-110 ms profiled in the window, before).

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
    keys = _keys(bridge, items, struct, plain)
    groups: dict = {}             # key -> ({plain row id: evaluated row}, finished rows, {row id: (written, shown)}, lengths)
    heads = set()                 # where each group's first item sits (many.merge compares those itself)
    for n, (it, key) in enumerate(zip(items, keys)):
        if key not in groups:
            rows = bridge.sound_rows(it)
            ev = {r["id"]: r for r in rows if r["row"] == "param" and r["id"] in plain}
            done = inspect.musical_rows(it, rows, root)
            head = {r["id"]: (it.get(r["id"], _NONE), r["value"]) for r in done if r["id"] in ev}
            groups[key] = (ev, done, head, {i for i in head if inspect.by_length(it, i)})
            heads.add(n)
    differs = {i for i, (n, wid) in _WITNESS.items()      # last time's proof first: the same item most likely still differs
               if n < len(items) and items[n]["id"] == wid and _differs(items[n], i, groups[keys[n]], root)}
    todo = [i for i in groups[keys[0]][2] if i not in differs]    # (a row the first group lacks is left out: many.merge)
    for n, it in enumerate(items):
        if not todo:                            # every plain row known to differ: nothing left to read
            break
        if n in heads:
            continue
        g = groups[keys[n]]
        for i in [i for i in todo if _differs(it, i, g, root)]:
            differs.add(i)
            todo.remove(i)
            _WITNESS[i] = (n, it["id"])
    return many.merge([g[1] for g in groups.values()], differs)


_WITNESS: dict = {}                         # plain row id -> (place, item id) of the item last found to differ in it


def _differs(it: dict, i: str, g: tuple, root: dict) -> bool:
    """Does the item show another value in row `i` than its group's first item (False: a row its group lacks)? Alike
    items differ from each other only where one differs from its group's first, and many.merge compares the firsts.
    A value written as the first's is shown as it, but for a length (in beats: as long as the tempo where it starts
    says), so most items need no showing (a hit's Pan left out, like every other hit's: 1,724 shown a merge before)."""
    ev, _, head, lengths = g
    if i not in head:
        return False
    raw, was = it.get(i, _NONE), head[i]
    if type(raw) is type(was[0]) and raw == was[0] and i not in lengths:
        return False
    return _value(it, ev[i], root) != was[1]


def _value(it: dict, r: dict, root: dict):
    """The item's value in row `r` as its own rows would show it (rows.evaluate, then inspect.musical_row)."""
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


_KEYS: dict = {}                            # item id -> (item, its parent, its page, its facts, its key): kept between merges
_SAME: dict = {}                            # facts and pages, one object per value: a kept one is told by identity
_LAYOUT: list = [None]                      # the layout those keys were made for (struct, plain)


def _keys(bridge, items: list[dict], struct: list, plain: list) -> list:
    """Each item's group key (`_key`; an item of another kind: its place, a group of its own). A key is kept while
    the item and its parent are the very same objects, its page shows the same and the layout is the same: a note's
    facts are its track's (doc/kind.py facts), so a pick of the same notes again makes no key twice. A change writes
    new items and a new parent (rostrum_core/edits.py): a note that changed only in plain values, written in the same
    type (a move: `at`), under a track with the same facts keeps its key too (`_alike`). A whole-song Right made 3,607
    keys again (~3.5 µs each; 20-50 ms of the merge profiled); now it compares each note's few fields."""
    layout = (tuple(struct), tuple(plain))
    if _LAYOUT[0] != layout or len(_KEYS) > 100_000:
        _KEYS.clear()
        _SAME.clear()
        _LAYOUT[0] = layout
    idx, out, pages, facts, loose = bridge.doc.locs(), [], {}, {}, (set(plain), set(struct))
    for n, it in enumerate(items):
        t = it["type"]
        if t not in FOLDED:
            out.append(n)
            continue
        loc = idx.get(it["id"])
        parent = idx[loc.parent].item if loc is not None and loc.parent in idx else None
        page = pages.get(t)                 # a note's or a hit's page is its kind's (onpage.py; only a clip's is its own)
        if page is None:
            p = frozenset(bridge.on_page(it))
            page = pages[t] = _SAME.setdefault(p, p)
        kept = _KEYS.get(it["id"])
        if kept is not None and kept[0] is it and kept[1] is parent and kept[2] is page:
            out.append(kept[4])
            continue
        f = facts.get((t, id(parent)))      # a note's facts are its track's, a hit's none: once a track
        if f is None:
            f = tuple(sorted(bridge.facts_of(it).items()))
            f = facts[(t, id(parent))] = _SAME.setdefault(f, f)
        if kept is not None and kept[2] is page and kept[3] is f and (kept[0] is it or _alike(kept[0], it, *loose)):
            key = kept[4]
        else:
            key = _key(it, struct, plain, page, f)
        _KEYS[it["id"]] = (it, parent, page, f, key)
        out.append(key)
    return out


def _alike(old: dict, new: dict, plain: set, struct: set) -> bool:
    """`new` is `old` with only plain values changed, each written in the same type, or fields no key reads: the
    same key. (An edit writes a new value and keeps every other one: a value not changed is the very same object.)"""
    if len(old) != len(new):
        return False
    for k, v in new.items():
        o = old.get(k, _NONE)
        if o is not v and (o is _NONE or k in struct or (k in plain and type(o) is not type(v))):
            return False
    return True


def _key(it: dict, struct: list, plain: list, page: frozenset, facts: tuple) -> tuple:
    """What the item's rows are made of but for their values: its facts, what its page shows elsewhere, its fields
    that decide which rows apply, and the type each plain value is written in (a time written in beats is shown as
    bars.beats). Written values, not shown ones: the same written value is always shown the same (but a length)."""
    return (it["type"], facts, page,
            tuple(_frozen(it.get(n)) for n in struct), tuple(type(it.get(n)) for n in plain))


def _frozen(v):
    try:
        hash(v)
        return type(v), v
    except TypeError:
        return type(v), repr(v)
