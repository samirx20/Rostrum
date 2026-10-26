"""Pinned to frame and Depth from the screen (2d-camera SPEC §4.9, §4.10, §5 #11 #13, §6): on a scene's own layer the
Depth group's switch and field, Set depth ▾ and ⋯ Pin to frame / Unpin from frame go through `layer.pin` and
`layer.set_depth` with keep "shown": the layer stays where it shows at the playhead, one change (a keyed depth gets
its key there: the operation's own rule). `at` is the playhead in scene seconds, as the operations read it.

`edit_call` is read by hooks.py, `facts` and `data` by action_rules.Facts and actions.py, `depth_calls` by the
`depth` rule (Set depth ▾ and its typed popover). No Qt.
"""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum2d.frame import TYPE as FRAME

from . import cover_move

FIELDS = ("screenLock", "depth")
WHY = "Pinning is for a scene's own layers (not the frame, not inside a group)."


def _own(doc, id_: str) -> bool:
    """A scene's own layer (Depth and Pinned mean something there): its parent is the scene, and it is not the frame."""
    it = doc.item(id_)
    return it["type"] != FRAME and doc.item(doc.parent_of(id_)[0])["type"] == "comp" and F.param(it["type"], "screenLock") is not None


def _keep(at: float) -> dict:
    return {"keep": "shown", "at": round(float(at), 6)}


def edit_call(doc, item_id: str, param: str, value, at: float) -> dict | None:
    """The Depth group's call for this edit, or None when it is not one (another field, a layer inside a group).
    `at`: the playhead in scene seconds."""
    if param not in FIELDS or not _own(doc, item_id):
        return None
    if param == "depth":
        return {"op": "layer.set_depth", "target": [item_id], "args": {"depth": round(float(value), 6), **_keep(at)}}
    return {"op": "layer.pin", "target": [item_id], "args": {"on": bool(value), **_keep(at)}}


def depth_calls(f, value: float) -> list[dict]:
    """Set depth: each picked layer goes to this depth where it shows now (`layer.set_depth`), then those Cover the
    frame's move applies to (cover_move.targets: still, not pinned, the frame moves) are made to cover everything the
    frame shows of them over the shot at the new depth (`background.fit`; a drawing that covers already is left as it
    is): one change; none when every layer is already there."""
    todo = [i for i, it in zip(f.ids, f.items) if it.get("depth", 0.0) != value]
    if not todo:
        return []
    fit = cover_move.targets(f.doc, todo)
    return [{"op": "layer.set_depth", "target": todo, "args": {"depth": value, **_keep(f.state.get("now", 0.0))}},
            *([{"op": "background.fit", "target": fit, "args": {}}] if fit else [])]


def facts(f) -> dict:
    """Pin to frame's facts (action_rules.Facts): `_own` for every picked layer, asked once per kind and per parent."""
    ok = bool(f.ids) and FRAME not in f.kinds and all(F.param(k, "screenLock") is not None for k in f.kinds) and all(
        f.doc.item(p)["type"] == "comp" for p in {w[0] for w in f.where.values()})
    pinned = [bool(it.get("screenLock")) for it in f.items]
    return {"pin_ok": ok, "any_pinned": ok and any(pinned), "any_unpinned": ok and not all(pinned)}


def calls(f, on: bool) -> list[dict]:
    """Pin / unpin each picked layer that is not so yet, kept where it shows at the playhead (one change)."""
    todo = [i for i, it in zip(f.ids, f.items) if bool(it.get("screenLock")) != on]
    return [{"op": "layer.pin", "target": todo, "args": {"on": on, **_keep(f.state.get("now", 0.0))}}] if todo else []


def data(a) -> list[dict]:
    """⋯ Pin to frame / Unpin from frame (made with actions._a): only the one that applies."""
    return [a("pin", "Pin to frame", rank=74, group="arrange", when={"fact": "any_unpinned"},
              calls={"rule": "pin", "on": True}, why=WHY),
            a("unpin", "Unpin from frame", rank=74, group="arrange", when={"fact": "any_pinned"},
              calls={"rule": "pin", "on": False}, why=WHY)]
