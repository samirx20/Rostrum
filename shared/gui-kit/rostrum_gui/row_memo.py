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
"""
from __future__ import annotations

from rostrum_core.conditions import refs

from . import pairs, rows as R

LIMIT = 4000                    # entries kept (a whole-song selection in Sound is thousands of notes)


class Entry:
    __slots__ = ("item", "stamp", "facts", "changed", "gone", "rows", "sig", "values", "fields", "near", "_shape")

    def __init__(self, item, stamp, facts, seen, rows):
        self.item, self.stamp, self.facts = item, stamp, facts
        self.changed, self.gone = seen.get("changed", frozenset()), seen.get("gone", frozenset())
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

    def put(self, item_id: str, item, stamp, facts, seen: dict, rows: list[dict]) -> Entry:
        """Keep the item's rows as just worked out (`seen`: the changed groups rows.evaluate told, the fields shown
        elsewhere on the page)."""
        if len(self.entries) >= LIMIT:
            self.entries.clear()
        e = self.entries[item_id] = Entry(item, stamp, facts, seen, rows)
        return e

    def _patched(self, e: Entry, item, redo) -> bool:
        """Patch the entry's rows for its pending fields (False: they must be worked out whole)."""
        fields, e.fields, e.near, e.item = e.fields, set(), False, item
        static = e.stamp[0]
        deciders, params, folds_of = _laid(static)
        if fields & deciders:
            return False
        at, holds, pair = e.shape()
        ids = {i for i in fields if i in at}
        ids |= {h for i in ids if i in pair for h in pair[i]}
        folds = {id(f): f for i in fields for f in folds_of.get(i, ())}
        if not ids and not folds:
            return True
        new, shown, starts, anim, gone = redo(item, [e.rows[at[i]] for i in ids])
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


def _sig(rows: list[dict]) -> tuple:
    """What many.merge reads of an item's rows besides their values: which rows, which apply and show, key marks,
    expressions, which groups are open."""
    return tuple(map(_row_sig, rows))


def _row_sig(r: dict) -> tuple:
    return r["id"], r.get("holds"), r.get("valid"), r.get("open"), r.get("anim"), repr(r.get("expr") or "")


_LAID: dict = {}


def _laid(static) -> tuple:
    """(the fields that decide which of this layout's rows show, not just what one shows; its params by id; the fold
    rows each field is a member of), worked out once a layout."""
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
        got = _LAID[id(static)] = (static, (frozenset(deciders), params, folds_of))
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
