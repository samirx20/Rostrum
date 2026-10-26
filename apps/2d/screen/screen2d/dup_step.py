"""Ctrl+D again repeats your last move. The step is read from the document's history and from nothing else, so it is never stale:
the newest changes are a duplicate (or an Alt+drag copy) of A into B, then only move / turn / scale changes on B, and B is what is
picked. Only a change that called layer.duplicate is a copy: a shape just drawn, a text, a paste or an import is inserted
after the layer under it too, but it is no copy of it (round 7: Ctrl+D after drawing threw the copy 460 px away). The step is B against A now, and `step` gives it as layer.duplicate's arguments (by_x, by_y, by_turn, by_scale). Anything
else changed since, or another pick, and there is no step: Ctrl+D is the plain 24 px one."""
from __future__ import annotations

from rostrum2d.ops_nudge import NUDGE
from rostrum_core.edits import Insert, Set

TRANSFORM = ("x", "y", "rotation", "scale")


def step(doc, ids: list[str]) -> dict:
    """layer.duplicate's step arguments for a copy of the picked layers ({} = none remembered)."""
    h, mine = doc.history, set(ids)
    for c in reversed(h.changes):
        if not c.original or not h.done.get(c.seq):
            continue                                            # an undo or redo record, or a change taken back
        inserts = [e for e in c.edits if isinstance(e, Insert)]
        if inserts:
            return _between(doc, c, inserts, ids)
        if not all(isinstance(e, Set) and e.id in mine and e.path[0] in TRANSFORM for e in c.edits):
            return {}                                           # something else changed since
    return {}


def _between(doc, c, inserts, ids) -> dict:
    """The step from the original to the first picked copy, when this change made exactly the picked layers as copies. A copy
    that landed the plain way (24 px right and down, or the free place after it) carries no step of its own: only the moves
    since count. One that landed by a `by` step, or in an Alt+drag (moves inside the change), carries it all."""
    if not any(call.get("op") == "layer.duplicate" for call in c.calls):
        return {}                                           # a drawn shape, text, paste or import: nothing to repeat
    made = {e.id for e in inserts}
    tops = {e.id: e.after for e in inserts if e.parent not in made}
    if set(tops) != set(ids) or not all(isinstance(e, Insert) or (isinstance(e, Set) and e.id in made) for e in c.edits):
        return {}
    a, b = tops[ids[0]], ids[0]
    if not (isinstance(a, str) and doc.has(a) and doc.has(b)):
        return {}
    dragged = [e for e in c.edits if isinstance(e, Set) and e.id == b and e.path[0] in TRANSFORM]
    landed = {**next(e.item for e in inserts if e.id == b), **{e.path[0]: e.value for e in dragged}}
    first = _gap(doc.item(a), landed)
    total = _plus(first if dragged or not _plain(first) else (0, 0, 0, 1), _gap(landed, doc.item(b)))
    names = ("by_x", "by_y", "by_turn", "by_scale")
    return {k: round(v, 4) for k, v in zip(names, total) if abs(v - (1 if k == "by_scale" else 0)) > 1e-4}


def _gap(a: dict, b: dict) -> tuple:
    """From layer a to layer b: across, down, turn, and the factor of scale."""
    return (b.get("x", 0) - a.get("x", 0), b.get("y", 0) - a.get("y", 0), b.get("rotation", 0) - a.get("rotation", 0),
            b.get("scale", 1) / a["scale"] if a.get("scale") else 1)


def _plus(p: tuple, q: tuple) -> tuple:
    return (p[0] + q[0], p[1] + q[1], p[2] + q[2], p[3] * q[3])


def _plain(g: tuple) -> bool:
    """A step layer.duplicate takes by itself: whole 24 px steps right and down (ops_nudge.NUDGE)."""
    return abs(g[0] - g[1]) < 1e-4 and abs(g[0] / NUDGE - round(g[0] / NUDGE)) < 1e-4 and abs(g[2]) < 1e-4 and abs(g[3] - 1) < 1e-4


def words(args: dict) -> str:
    """A step in plain words for the message line: "120 px across", "30° turn"."""
    out = []
    for key, up, down in (("by_x", "across", "back"), ("by_y", "down", "up")):
        if args.get(key):
            out.append(f"{abs(args[key]):g} px {up if args[key] > 0 else down}")
    if args.get("by_turn"):
        out.append(f"{abs(args['by_turn']):g}° turn")
    if args.get("by_scale"):
        out.append(f"{args['by_scale'] * 100:g}% size each")
    return ", ".join(out)
