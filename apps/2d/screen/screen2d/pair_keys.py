"""The two halves of one setting (Tilt X | Y, Anchor X | Y …: rostrum_gui.pairs) keep keys only on a half that changes.
No Qt.

The pair is ONE setting on screen (one row, one key mark): it is animated when either half has keys. Underneath, a
half that holds one value while its partner moves needs no keys, so:
- the key mark keys only the animated half once the other is still (`rides`: the still half reads as its partner's
  state, `animate_calls` gives it nothing);
- a typed value on one half that makes it move drops the other half's keys when they all hold one value (`typed_calls`:
  key.clear keeps that value as its still value), so a Tilt Y flip leaves no Tilt X keys holding 0;
- a typed value on the still half of an animated pair keys it, with its old value at the partner's key times first, so
  it changes from here on as if it had been keyed all along (never its value everywhere at once).
Position follows the same rules for a typed value (the diamond keys X and Y; type a new Y at another time and the X keys,
all holding one value, go: only Y is keyed). A drag on the canvas still writes both halves, as a move in two directions.
Size stays keyed together: resizing on the canvas writes width and height at once.
"""
from __future__ import annotations

from rostrum_core.keys import key_value, keys_of
from rostrum_core.keys.marked import marked
from rostrum_gui.pairs import PAIRS

TOGETHER = {"w", "h", "width", "height"}
PARTNER = {**{a: b for a, b in PAIRS}, **{b: a for a, b in PAIRS}}


def partner(prop: str) -> str | None:
    return PARTNER.get(prop)


def rides(item: dict, prop: str) -> str | None:
    """The animated partner of this still half (its key mark follows that half's), or None."""
    other = PARTNER.get(prop)
    return other if other and not keys_of(item, prop) and keys_of(item, other) else None


def _one_value(keys: list[dict]) -> bool:
    return bool(keys) and not any(marked(k) for k in keys) and all(key_value(k) == key_value(keys[0]) for k in keys)


def typed_calls(item: dict, prop: str, value, at: float, call: dict) -> list[dict]:
    """The calls for a typed `value` on `prop` of `item` (the document's item: its own seconds) at `at`, given the plain
    call the route made (value.set): that call, with the pair's tidying around it (module doc)."""
    other = PARTNER.get(prop)
    if not other or prop in TOGETHER or call.get("op") != "value.set" or isinstance(value, (bool, str)):
        return [call]
    mine, theirs = keys_of(item, prop), keys_of(item, other)
    if not mine and theirs:                          # a still half of an animated pair: keyed from here, as it was before
        was = item.get(prop)
        if not isinstance(was, (int, float)) or any(marked(k) for k in theirs):
            return [call]
        before = [{"op": "key.add", "target": [item["id"]], "args": {"prop": prop, "t": k["t"], "v": was}}
                  for k in theirs if abs(k["t"] - at) > 1e-6]
        return [*before, call]
    moves = any(not marked(k) and abs(k["t"] - at) > 1e-6 and key_value(k) != value for k in mine)
    if moves and _one_value(theirs):                 # this half moves now; the other's keys hold one value: not needed
        return [call, {"op": "key.clear", "target": [item["id"]], "args": {"prop": other, "at": at}}]
    return [call]
