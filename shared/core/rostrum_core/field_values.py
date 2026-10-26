"""Stored field values against their fields' own rules (DocKind.bad_values): the same rule operation arguments obey,
so no field of any kind can hold what its control could never set (a frame rate of 0)."""
from __future__ import annotations

from .errors import RostrumError, codes
from .tree import fields

_PLAIN = (str, int, float, bool)
_GONE = object()


def _seen_key(kind, name, value):
    """What a passed value is remembered by (None: not remembered): a plain value with its type, or a one-key dict of
    a plain value (a time {"beat": 8.0}: a whole-song move checks ~1,800 distinct of 3,352), types kept so 1 and 1.0
    are told apart. Checks are pure: the same value of the same field passes the same way."""
    t = type(value)
    if t in _PLAIN:
        return kind, name, t, value
    if t is dict and len(value) == 1:
        for k, v in value.items():
            if type(v) in _PLAIN:
                return kind, name, k, type(v), v
    return None


def _plan(op, names: dict) -> tuple[list, list]:
    """(fields only moved by a Shift whose number has a range to ask: [(name, path inside, lo, hi)], fields checked
    whole: [name]) for one kind and one `only` entry (a whole-song Shift's 3,607 items share one: planned once)."""
    moved, whole = [], []
    for name, sub in names.items():
        p = op.param(name)
        b = p.shift_bounds(sub) if sub is not None and p is not None and hasattr(p, "shift_bounds") else None
        if b is None:
            whole.append(name)
        else:
            moved.append((name, sub, b[0], b[1]))
    return moved, whole


def bad_values(registry, lists: dict, items, only=None):
    """Each stored field value its kind's own field op refuses (range, kind of value, choices). `only`: item id ->
    {field name: None (set: checked whole), or the path a Shift moved a number at inside it} (run.set_fields; an item
    not in it: all its fields). A Shift only moves a number, so a moved value that passed keeps its form and only its
    range is asked (Param.shift_bounds; out of range: checked whole, the same words): a whole-song nudge asked 3,607
    full checks, ~10 ms, now two comparisons each. Yields RostrumErrors."""
    ops, params, passed, plans = {}, {}, set(), {}  # per kind / (kind, field) / (kind, only entry): asked once, not
                                                    # per item; plain values that passed (3,000 notes share a few pitches)
    for item in items:
        kind = item.get("type")
        op = ops.get(kind, _GONE)
        if op is _GONE:
            op = ops[kind] = registry.field_op(kind)
        if not op:
            continue
        names = only.get(item.get("id")) if only else None
        if names is None:
            todo = fields(item, lists).items()
        else:
            key = kind, id(names)                   # (`only` keeps every entry alive while we run)
            plan = plans.get(key)
            if plan is None:
                plan = plans[key] = _plan(op, names)
            todo = [(n, item[n]) for n in plan[1] if n in item] if plan[1] else None
            for name, sub, lo, hi in plan[0]:       # (the number at `sub`: a number from lo to hi, NaN is not)
                value = n = item.get(name, _GONE)
                if value is _GONE:
                    continue
                for k in sub:
                    n = n.get(k, _GONE) if type(n) is dict else _GONE
                if not ((type(n) is float or type(n) is int) and lo <= n <= hi):
                    todo = (todo or []) + [(name, value)]
            if not todo:
                continue
        for name, value in todo:
            p = params[kind, name] if (kind, name) in params else params.setdefault((kind, name), op.param(name))
            if p is None or value in getattr(p, "kept", ()):   # a kept choice: an old file's, still read
                continue
            seen = _seen_key(kind, name, value)
            if seen in passed:
                continue
            where = f'{item.get("type")} "{item.get("id")}"'
            try:
                stored = p.check(value, where)
            except RostrumError as e:
                yield e
                continue
            if stored != value:     # checks take forms people write ("#fff"); a file holds only the stored one
                yield RostrumError(codes.BAD_ARGUMENT, where, f"{name}={value!r}", "is not written as stored", [repr(stored)])
            elif seen is not None:
                passed.add(seen)
