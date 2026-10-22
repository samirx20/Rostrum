"""Attach to bone (UX_SPEC 3.23 "Bones and attaching"): parts attach by themselves (rig.guess_bones, by nearness); to fix
one, select the part, Ctrl+click a bone on the overlay (rig_view.pickBone), and the context bar offers Attach to bone.
One change: the part's bind moves to that bone (rigid: `bind.set`), or a new bind (`bind.add`), the operations agents
call. Read on the selection as the kit holds it (a bone is not a layer). No Qt.
"""
from __future__ import annotations


def pair(doc, picked: list[str]) -> tuple[str, str, str] | None:
    """(rig, part, bone) when `picked` is one bone and one layer straight inside that bone's rig, else None."""
    if len(picked) != 2 or not all(doc.has(i) for i in picked):
        return None
    bones = [i for i in picked if doc.item(i)["type"] == "bone"]
    if len(bones) != 1:
        return None
    bone = bones[0]
    part = next(i for i in picked if i != bone)
    rig = doc.parent_of(bone)[0]
    if part not in {lay["id"] for lay in doc.item(rig).get("layers", [])}:
        return None
    return rig, part, bone


def calls(doc, picked: list[str]) -> list[dict]:
    """The one change ([] when it is already attached there, rigidly, or the selection is not a part and a bone)."""
    found = pair(doc, picked)
    if found is None:
        return []
    rig, part, bone = found
    bind = next((b for b in doc.item(rig).get("binds", []) if b["layer"] == part), None)
    if bind is None:
        return [{"op": "bind.add", "target": [rig], "args": {"layer": part, "bone": bone}}]
    if bind["bone"] == bone and not bind.get("bone2"):
        return []
    return [{"op": "bind.set", "target": [bind["id"]], "args": {"bone": bone, "bone2": ""}}]
