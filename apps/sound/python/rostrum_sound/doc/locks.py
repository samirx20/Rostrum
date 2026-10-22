"""Locked tracks (`track.set {locked}`): no operation may change a locked track or anything on it, for anyone (a
person, an agent, a script), until it is unlocked. One guard around every operation of the Sound registry (`guard`,
called once by kind.py after the operations registered): after an operation runs, any edit inside a locked track
refuses the whole call with a plain sentence. Unlocking itself (only `locked` set on the track) always passes.
"""
from __future__ import annotations

import dataclasses

from rostrum_core import codes
from rostrum_core import edits as E


def _track(ctx, id_):
    """The track an id sits in (itself when it is one), or None."""
    while id_ in ctx.idx:
        loc = ctx.idx[id_]
        if loc.item.get("type") == "track":
            return loc.item
        id_ = loc.parent
    return None


def _places(e):
    """The ids an edit touches, to find its track: the item, or (removed / inserted / moved) where it was or went."""
    if isinstance(e, E.Set):
        return [e.id]
    if isinstance(e, E.Insert):
        return [e.parent]
    if isinstance(e, E.Remove):
        return [e.parent]
    return [e.from_[0] if e.from_ else "", e.to[0] if e.to else ""]


def _check(ctx, done_before: int):
    for e in ctx.edits[done_before:]:
        if isinstance(e, E.Set) and e.path and e.path[0] == "locked":
            continue
        gone = e.item if isinstance(e, E.Remove) and e.item.get("type") == "track" else None
        for place in _places(e) + ([e.id] if gone else []):
            t = gone if gone is not None and place == e.id else _track(ctx, place)
            if t is not None and t.get("locked"):
                name = t.get("name") or t["id"]
                ctx.fail(codes.CONFLICT, f'track "{name}"', "is locked: nothing on it can change",
                         hint="Unlock it first (Ctrl+Shift+L, or its lock on the track header).")


def _guarded(fn):
    def run(ctx, targets, args):
        before = len(ctx.edits)
        fn(ctx, targets, args)
        _check(ctx, before)
    run.__wrapped__ = fn
    return run


def guard(registry) -> None:
    for op in registry.ops():
        if not hasattr(op.fn, "__wrapped__"):
            registry._ops[op.name] = dataclasses.replace(op, fn=_guarded(op.fn))
