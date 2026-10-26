"""Each item's settings rows, kept between picks and patched after a change, and many items folded into one panel
(no Qt).

48 layers picked worked out ~125 rows for each of them on every pick (which apply, their values, key marks): ~5 ms an
item, ~250 ms a Ctrl+A. Now:
- An item's rows (rows.evaluate, then rows.omit) are kept (`Memo`) while what they were read from holds: the panel's
  state (`stamp`: layout, More, folds, search, and what an app's rows read that no change announces, the playhead) and
  the item itself. A change (touched.fields_of) that names the fields of it that changed leaves its entry in place
  with those fields pending; a change that can't say that narrowly (an add, a remove, a rename, an item above it
  changed) drops it. A change to a neighbour (another item with the same parent: a camera beside a layer) marks the
  entry's facts to be read again.
- Pending fields are patched, never the whole list: only those fields' rows get their value, key mark and
  expression read again (rows._values), as a drag's step does. A field that decides which rows show (named by a
  valid-when, a switch, a "shown while changed" rule, a pick or a list, what pairs.READS reads), facts that read
  otherwise, or a folded group that opens or closes: the item's rows are worked out whole.
- Many items (`fold`): items whose rows are alike in everything but their values are one group; each group's rows
  are compared column by column (value by value, in C), and many.merge folds the groups' first rows with the rows
  that differ marked: exactly many.merge of every item's rows, at the cost of a few groups. Sound's many_rows does
  the same for thousands of notes, from their fields.
- An item with no entry (a Ctrl+A over 200 layers after an add: every entry dropped) borrows an alike item's rows
  (`borrow`): an entry of the same kind and place (2D: parent), worked out for the same panel state, facts, starts and
  fields shown elsewhere, whose values of every field that decides which rows show (valid-when, switch, "shown while
  changed", pick and list fields, pairs.READS) are this item's own, so every row's valid-when holds the same for this
  item, decided by its own values. Only the fields where the two differ (values, keys, shown values) are patched, as
  after a change; a pick's or list's options are the item's own (a sibling pick leaves the item itself out). Anything
  else differing (an expression, a child list) works it out whole. A donor is only ever a kept entry that holds now
  (nothing pending): a dropped or pending entry lends nothing.
"""
from __future__ import annotations

from rostrum_core.conditions import refs

from . import pairs, rows as R

LIMIT = 4000                    # entries kept (a whole-song selection in Sound is thousands of notes)


class Entry:
    __slots__ = ("item", "stamp", "facts", "changed", "gone", "rows", "sig", "values", "fields", "near", "_shape",
                 "shown", "starts")

    def __init__(self, item, stamp, facts, seen, rows):
        self.item, self.stamp, self.facts = item, stamp, facts
        self.changed, self.gone = seen.get("changed", frozenset()), seen.get("gone", frozenset())
        self.shown, self.starts = seen.get("shown"), seen.get("starts")      # (what `borrow` compares; None: lends nothing)
        self.rows, self.sig, self.values = rows, _sig(rows), tuple(r.get("value") for r in rows)
        self.fields, self.near = set(), False        # fields changed since; a neighbour changed (facts to read again)
        self._shape = None

    def shape(self) -> tuple:
        """({param id: its place}, {param id: applies}, {half's id: both halves' ids}): what a patch leaves as it is,
        read once."""
        if self._shape is None:
            at = {r["id"]: n for n, r in enumerate(self.rows) if r["row"] == "param"}
            pair = {}
            for r in self.rows:
                if r.get("half") == "first":
                    pair[r["id"]] = pair[r["partner"]] = (r["id"], r["partner"])
            self._shape = (at, {i: self.rows[n]["holds"] for i, n in at.items()}, pair)
        return self._shape


class Memo:
    def __init__(self):
        self.entries: dict[str, Entry] = {}
        self.donors: dict = {}              # (place, the deciding fields' values) -> the item id last kept there

    def heard(self, doc, touched) -> None:
        """After every document change or drag step: drop what it may have changed, note the fields it changed."""
        if touched is None or touched.structural:
            self.entries.clear()
            return
        idx = doc._index()
        near = {idx[i].parent for i in touched.ids if i in idx}
        for i, e in list(self.entries.items()):
            loc = idx.get(i)
            f = touched.fields_of(doc, i) if loc is not None else None
            if f is None:
                del self.entries[i]
                continue
            e.fields |= f
            e.near = e.near or loc.parent in near

    def clear(self) -> None:
        self.entries.clear()
        self.donors.clear()

    def get(self, item_id: str, item, stamp, facts_of, redo) -> Entry | None:
        """The kept entry for this item if it still holds (its pending fields patched), else None. `redo(item, rows)`:
        those rows' values, key marks and expressions read again (rows._values) -> (new rows, shown values,
        starts, anim, the fields shown elsewhere)."""
        e = self.entries.get(item_id)
        if e is None or e.stamp != stamp:
            return None
        if e.item is item and not e.fields and not e.near:
            return e
        if e.item is not item and not e.fields:     # changed and not told how: work it out whole
            return None
        facts = facts_of(item)
        if facts != e.facts or not self._patched(e, item, redo):
            del self.entries[item_id]
            return None
        e.facts = facts
        return e

    def put(self, item_id: str, item, stamp, facts, seen: dict, rows: list[dict], place=None) -> Entry:
        """Keep the item's rows as just worked out (`seen`: the changed groups rows.evaluate told, the fields shown
        elsewhere on the page, and its shown values and starts: then alike items at `place` may borrow them)."""
        if len(self.entries) >= LIMIT:
            self.clear()
        e = self.entries[item_id] = Entry(item, stamp, facts, seen, rows)
        if place is not None and e.shown is not None:
            self.donors[(place, _decided(stamp[0], e.shown))] = item_id
        return e

    def borrow(self, item_id: str, item, stamp, place, facts, shown, starts, gone, redo, choices) -> Entry | None:
        """The item's entry made from an alike item's (module doc), kept; None: none to borrow from, or it must be
        worked out whole. `place`: what alike items share besides their kind's layout (2D: their parent); `shown`,
        `starts`, `gone`: the item's shown values, its kind's starts, the fields shown elsewhere; `redo` as in `get`;
        `choices(row id)`: the item's own options for a list or a pick."""
        key = (place, _decided(stamp[0], shown))
        d = self.entries.get(self.donors.get(key, ""))
        if (d is None or d.shown is None or d.fields or d.near or d.stamp != stamp or d.gone != gone
                or d.starts != starts or d.facts != facts):
            return None
        _, params, _, _, chosen = _laid(stamp[0])
        differ = _differ(item, d.item, shown, d.shown, params)
        if differ is None:
            return None
        e = Entry.__new__(Entry)
        for name in Entry.__slots__:
            setattr(e, name, getattr(d, name))
        e.fields, e.near, e.shown = differ, False, shown
        if not self._patched(e, item, redo) or not _own_choices(e, chosen, choices):
            return None
        e.shown, e.starts = shown, starts           # (the item's own, read just now: it may lend in turn)
        self.entries[item_id] = e
        self.donors[key] = item_id
        return e

    def _patched(self, e: Entry, item, redo) -> bool:
        """Patch the entry's rows for its pending fields (False: they must be worked out whole)."""
        fields, e.fields, e.near, e.item = e.fields, set(), False, item
        static = e.stamp[0]
        deciders, params, folds_of, _, _ = _laid(static)
        if fields & deciders:
            return False
        at, holds, pair = e.shape()
        ids = {i for i in fields if i in at}
        ids |= {h for i in ids if i in pair for h in pair[i]}
        folds = {id(f): f for i in fields for f in folds_of.get(i, ())}
        if not ids and not folds:
            if fields:
                e.shown = None                      # (what it showed was compared at put: it lends no more)
            return True
        new, shown, starts, anim, gone = redo(item, [e.rows[at[i]] for i in ids])
        if e.shown is not None:
            e.shown, e.starts = shown, starts       # a lender is compared by what it shows now, never what it showed
        if gone != e.gone:
            return False                            # (the page shows another field itself now: whole)
        if any(R.changed(f, params, shown, holds, starts, anim) != (f["fold"] in e.changed) for f in folds.values()):
            return False                            # a folded group that opens or closes: whole
        out, sig, values = list(e.rows), list(e.sig), list(e.values)
        for r in new:
            out[at[r["id"]]] = r
        for i in ids:                               # a pair's halves read together (pairs.pair_valid)
            if i in pair and pair[i][0] == i:
                pairs.pair_valid(out[at[i]:at[i] + 2], shown)
        for i in ids:
            n = at[i]
            sig[n], values[n] = _row_sig(out[n]), out[n].get("value")
        e.rows, e.sig, e.values = out, tuple(sig), tuple(values)
        return True


def _own_choices(e: Entry, chosen: tuple, choices) -> bool:
    """The entry's list and pick rows (`chosen`: (id, is a pick, its "None" entries)) given the item's own options
    (rows.evaluate's: a pick shows as a choice). False: a pick has choices for one item and none for the other (whether
    it applies differs): whole."""
    at, out = e.shape()[0], None
    for i, pick, none in chosen:
        if i not in at:
            continue
        row, mine = e.rows[at[i]], choices(i)
        if pick:
            if bool(mine) != (len(row["options"]) > none):
                return False
            mine = row["options"][:none] + mine
        if mine != row["options"]:
            out = out or list(e.rows)
            out[at[i]] = {**row, "options": mine}
    if out is not None:
        e.rows = out
    return True


_NONE = object()
OWN = frozenset({"id"})         # what every item has its own of and no row reads


def _decided(static, shown: dict) -> tuple:
    """The values of the fields that decide which of this layout's rows show (hashable)."""
    return tuple(_hashable(shown.get(n, _NONE)) for n in _laid(static)[3])


def _hashable(v):
    try:
        hash(v)
        return v
    except TypeError:
        return repr(v)


def _differ(item: dict, was: dict, shown: dict, was_shown: dict, params: dict) -> set | None:
    """The fields where two alike items differ, as a change would name them (touched.fields_of): a field's own value,
    its shown value, or its keys (the one animation model: an owner's `keys`, each naming its `prop`; the keys' ids are
    each item's own). None: they differ in something no field names (an expression, a child list): whole. A row reads
    its field's shown value, never its stored one: those are compared for the fields with rows."""
    if shown.keys() != was_shown.keys():
        return None
    out = {k for k, a in shown.items() if not (a is was_shown[k] or a == was_shown[k])}
    for k in (item.keys() | was.keys()) - params.keys() - OWN:
        a, b = item.get(k, _NONE), was.get(k, _NONE)
        if a is b or a == b:
            continue
        if not (isinstance(a, list) or isinstance(b, list)):
            out.add(k)
        elif k == "keys" and isinstance(a, list) and isinstance(b, list):
            mine, theirs = _by_prop(a), _by_prop(b)
            out |= {p for p in mine.keys() | theirs.keys() if mine.get(p) != theirs.get(p)}
        elif _plain(a) != _plain(b):
            return None
    return out


def _by_prop(keys: list) -> dict:
    out: dict = {}
    for k in keys:
        out.setdefault(k.get("prop") if isinstance(k, dict) else None, []).append(_plain(k))
    return out


def _plain(v):
    """A child list's contents without the children's own ids."""
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items() if k != "id"}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    return v


def _sig(rows: list[dict]) -> tuple:
    """What many.merge reads of an item's rows besides their values: which rows, which apply and show, key marks,
    expressions, which groups are open."""
    return tuple(map(_row_sig, rows))


def _row_sig(r: dict) -> tuple:
    return r["id"], r.get("holds"), r.get("valid"), r.get("open"), r.get("anim"), repr(r.get("expr") or "")


_LAID: dict = {}


def _laid(static) -> tuple:
    """(the fields that decide which of this layout's rows show, not just what one shows; its params by id; the fold
    rows each field is a member of; the deciders in order; the list and pick rows (id, is a pick, its "None"
    entries)), worked out once a layout."""
    got = _LAID.get(id(static))
    if got is None or got[0] is not static:
        if len(_LAID) > 64:
            _LAID.clear()
        deciders, folds_of = set(pairs.READS), {}
        for r in static:
            deciders |= {n for kind, n in refs(r.get("valid_when")) if kind == "param"}
            if r.get("switch"):
                deciders.add(r["switch"])
            if r["row"] == "param" and (r.get("shown") == "changed" or r["type"] == "list" or r.get("control") == "pick"):
                deciders.add(r["id"])
            if "fold" in r:
                for m in r["members"]:
                    folds_of.setdefault(m, []).append(r)
        params = {r["id"]: r for r in static if r["row"] == "param"}
        chosen = tuple((i, r.get("control") == "pick", 1 if r["default"] == "" else 0) for i, r in params.items()
                       if r.get("control") == "pick" or (r["type"] == "list" and r["item"] != "choice"))
        got = _LAID[id(static)] = (static, (frozenset(deciders), params, folds_of, tuple(sorted(deciders)), chosen))
    return got[1]


def fold(entries: list[Entry], merge) -> list[dict]:
    """One row list for many items (the first leads): alike items grouped, each group compared column by column,
    then `merge` (many.merge) over each group's first rows with the differing rows marked."""
    groups: dict = {}
    for e in entries:
        groups.setdefault(e.sig, []).append(e)
    differs = set()
    for g in groups.values():
        if len(g) < 2:
            continue
        ids = [r["id"] for r in g[0].rows]
        for n, col in enumerate(zip(*(e.values for e in g))):
            if col.count(col[0]) != len(col):
                differs.add(ids[n])
    return merge([g[0].rows for g in groups.values()], differs)
