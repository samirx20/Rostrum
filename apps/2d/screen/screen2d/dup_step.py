"""Ctrl+D again repeats your step, as Illustrator's and Figma's duplicate again do. The step is read from the document's
history and from nothing else, so it is never stale: the newest changes are a copy of A into B (Ctrl+D, or an Alt+drag,
whose record keeps its layer.duplicate call: rostrum_core.gesture), then only move / turn / scale changes on B, and B is
what is picked. The step is always B now against A, however B was made and moved since: Ctrl+D, drag the copy 300 px
right, Ctrl+D gives 300 px across, and each Ctrl+D after keeps adding it. Only a change that called layer.duplicate is a
copy: a shape just drawn, a text, a paste or an import is inserted after the layer under it too, but it is no copy of it
(round 7: Ctrl+D after drawing threw the copy 460 px away). `step` gives it as layer.duplicate's arguments (by_x, by_y,
by_turn, by_scale). Anything else changed since, or another pick, and there is no step: Ctrl+D is the plain 24 px one."""
from __future__ import annotations

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
    """The step from the original to the first picked copy now, when this change made exactly the picked layers as copies."""
    if not any(call.get("op") == "layer.duplicate" for call in c.calls):
        return {}                                           # a drawn shape, text, paste or import: nothing to repeat
    made = {e.id for e in inserts}
    tops = {e.id: e.after for e in inserts if e.parent not in made}
    if set(tops) != set(ids) or not all(isinstance(e, Insert) or (isinstance(e, Set) and e.id in made) for e in c.edits):
        return {}
    a, b = tops[ids[0]], ids[0]
    if not (isinstance(a, str) and doc.has(a) and doc.has(b)):
        return {}
    names = ("by_x", "by_y", "by_turn", "by_scale")
    return {k: round(v, 4) for k, v in zip(names, _gap(doc.item(a), doc.item(b))) if abs(v - (1 if k == "by_scale" else 0)) > 1e-4}


def _gap(a: dict, b: dict) -> tuple:
    """From layer a to layer b: across, down, turn, and the factor of scale."""
    return (b.get("x", 0) - a.get("x", 0), b.get("y", 0) - a.get("y", 0), b.get("rotation", 0) - a.get("rotation", 0),
            b.get("scale", 1) / a["scale"] if a.get("scale") else 1)


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
