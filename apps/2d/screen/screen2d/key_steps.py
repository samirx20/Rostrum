"""Scripted steps for picking keys in the timeline and A (steps.py hands these over). The same calls a click makes.

    keypick <key id>[,<key id>…] [ctrl|shift]   click a diamond (the ids it stands for); Ctrl adds / removes, Shift the run
    keydrag2 <key id> <from s> <to s>            press a picked key at <from>, let go at <to> (composition seconds): all move
    keydelete                                    Delete with keys picked
    showanim                                     A: the selection's animated settings only; again folds them
"""
from __future__ import annotations

WORDS = ("keypick", "keydrag2", "keydelete", "showanim")


def _row_of(bridge, key_id):
    for row in bridge.layers:
        groups = [k.get("ids", [k["id"]]) for k in row["keys"]]
        if any(key_id in g for g in groups):
            return groups
    return [[key_id]]


def do_key_step(bridge, word, rest, step):
    keys = bridge._keys
    if word == "keypick":
        ids = rest[0].split(",")
        keys.click(ids, rest[1] if rest[1:] else "", _row_of(bridge, ids[0]))
        print("keys", keys.ids)
    elif word == "keydrag2":
        if not keys.beginDrag(rest[0], float(rest[1])):
            raise RuntimeError(f"step {step!r}: {rest[0]} is not a picked key")
        keys.dragTo(float(rest[2]))
        keys.endDrag()
    elif word == "keydelete":
        bridge.layerCommand("delete")
    elif word == "showanim":
        bridge.showAnimated()
        print("rows", [r["label"] for r in bridge.layers])
