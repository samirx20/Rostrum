"""A range as an `edit_document` target: `{"track": "guitar", "from": {"bar": 1}, "to": {"bar": 9}}` stands for every
note (or drum hit, for a hit operation) of that track that STARTS in [from, to), so nobody lists ids.

The range is turned into ids in one place (`expand`), before the shared planner sees the call; the operation then runs
on those ids as it always did, and the history records the ids. A time is any time form ({"beat": 8}, seconds,
"#drop") or {"bar": n} (bars counted from 1, as the ruler shows them); `from` left out = the start, `to` left out =
the end. The ids are those of the document before the call: a later operation in the same call can't use a range over
notes an earlier one made. An empty range is a loud error that names where the track's notes are.
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes

from ..doc import meter, tempo, times
from ..doc.select_time import start_of

KEYS = {"track", "from", "to"}
SHAPE = '{"track": "guitar", "from": {"bar": 1}, "to": {"bar": 9}}'
LISTS = {"note": "notes", "hit": "hits"}
SCHEMA_ITEM = {"anyOf": [{"type": "string"}, {"type": "object", "required": ["track"], "additionalProperties": False, "properties": {
    "track": {"type": "string"}, "from": {}, "to": {}}}],
    "description": "An item id, or a range of one track's notes / hits by start time: " + SHAPE + " (from included, to not; bars count from 1)."}


def _seconds(root, value, where: str) -> float:
    if isinstance(value, dict) and set(value) == {"bar"}:
        bar = value["bar"]
        if isinstance(bar, bool) or not isinstance(bar, int) or bar < 1:
            raise RostrumError(codes.BAD_ARGUMENT, where, f"{value}", 'must be {"bar": n} with n a whole number from 1')
        return tempo.seconds_at(root, meter.bar_start(root, bar))
    why = times.problem(value)
    if why:
        raise RostrumError(codes.BAD_ARGUMENT, where, f"{value!r}", why, ["seconds (2.5)", '{"beat": 8}', '{"bar": 3}', '"#drop"'])
    return times.seconds(value, root, where)


def _bar(root, sec: float) -> str:
    return f"bar {meter.bar_at(root, tempo.beat_at(root, sec)) + 1:.2f} ({sec:.2f} s)"


def ids_in(doc, target: dict, kind: str, where: str) -> list[str]:
    """Ids of the track's notes / hits starting in the range; an empty range fails."""
    root = doc.data
    bad = sorted(set(target) - KEYS)
    if bad:
        raise RostrumError(codes.BAD_ARGUMENT, where, f'"{bad[0]}"', "is not part of a range target", sorted(KEYS), f"Shape: {SHAPE}")
    track = doc.item(target["track"]) if doc.has(target["track"]) else None
    if track is None or track.get("type") != "track":
        raise RostrumError.not_found(where, "track", target["track"], [t["id"] for t in root.get("tracks", [])])
    items = [(start_of(root, n), n["id"]) for n in track.get(LISTS[kind], [])]
    a = _seconds(root, target["from"], where) if "from" in target else 0.0
    b = _seconds(root, target["to"], where) if "to" in target else float("inf")
    found = [i for s, i in items if a - 1e-9 <= s < b - 1e-9]
    if not found:
        span = f"its {LISTS[kind]} start from {_bar(root, min(s for s, _ in items))} to {_bar(root, max(s for s, _ in items))}" if items \
            else f"it has no {LISTS[kind]}"
        raise RostrumError(codes.BAD_ARGUMENT, where, f'range of "{track["id"]}"', f"holds no {LISTS[kind]} ({span})",
                           hint="Widen from / to (a range is from included, to not; bars count from 1).")
    return found


def expand(doc, registry, calls: list) -> list:
    """`calls` with every range target written as the ids it stands for (other calls untouched)."""
    out = []
    for n, call in enumerate(calls, 1):
        target = call.get("target") if isinstance(call, dict) else None
        if not any(isinstance(t, dict) for t in (target if isinstance(target, list) else [target])):
            out.append(call)
            continue
        where = f"op {n} of {len(calls)} ({call.get('op')})"
        op = registry.get(registry.resolve([{**call, "target": [], "args": {}}])[0]["op"], where)
        kinds = [k for k in LISTS if op.targets and k in op.targets]
        if not kinds:
            raise RostrumError(codes.BAD_ARGUMENT, where, "a range target", f"{op.name} does not act on notes or hits",
                               hint="Name the ids it takes (inspect_operations).")
        ids: list[str] = []
        for t in target if isinstance(target, list) else [target]:
            ids += ids_in(doc, t, kinds[0], where) if isinstance(t, dict) else [t]
        out.append({**call, "target": ids})
    return out
