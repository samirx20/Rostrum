"""The right-click menu's one action list (SPEC §3.5). No Qt. `entries(doc, item_id, state)` gives only what applies
right now and what an existing operation can do, six at most: {value, label, keys}. item_id "" is empty space.

state: {"copied": the copied material's id or "", "shot_id": the open shot, "can_shot": a camera exists}.
Left out because no operation does it yet: Group (no op moves existing items into a group), Frame it (the viewport
can only go home to the shot camera), look through a camera (only lights), Paste of items (no item copy).
"""
from __future__ import annotations

from rostrum3d import fields as F

MAX = 6


def _e(value, label, keys=""):
    return {"value": value, "label": label, "keys": keys}


def entries(doc, item_id: str, state: dict) -> list[dict]:
    out: list[dict] = []
    if not item_id:
        out.append(_e("home", "Frame all", "Home"))
        if state.get("can_shot"):
            out.append(_e("shot", "New shot from this view"))
    elif doc.has(item_id):
        item = doc.item(item_id)
        kind = item["type"]
        if kind in F.ITEMS:
            out.append(_e("duplicate", "Duplicate", "Ctrl D"))
        if kind in F.ITEMS or kind == "part":
            out.append(_e("delete", "Delete", "Del"))
        if kind == "light":
            out.append(_e("look", "Look through"))
        if kind == "mesh":
            copied = state.get("copied", "")
            if copied and doc.has(copied) and item.get("material") != copied:
                out.append(_e("paste", "Paste material"))
            elif item.get("material"):
                out.append(_e("copy", "Copy material"))
    assert len(out) <= MAX, f"the context menu holds {MAX} at most, got {len(out)}"
    return out
