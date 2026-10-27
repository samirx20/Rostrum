"""Simulate on Rostrum3D's action list (brief 25, SPEC §10), as plain data read into actions3d.LIST. Right-click a shape
(or a combine, an import, a group, a clay, a copies item) › Simulate › Falls · Stays still · Off; the same three in
Ctrl+K and the rail's Simulate flyout (Rail3D.qml). Each is one change made of the operation an agent calls too
(`sim.body {targets, kind}`, rostrum3d/sim).

Menu room: the kit folds the three into one "Simulate ›" row (action_views.FOLD), so a single shape's right-click gains
one row and loses none (a shape with a material: eight). Folding it under Make copies would hide it where nobody looks;
dropping one of the others would take away something people use. The current kind carries the menu's ✓
(ContextMenu3D.qml reads backend.sim.kind), so all three stay: Off is how a body stops being one.

Only top-level items can be bodies (sim.body refuses an item inside a group, copies or rig): the actions are absent
for one. No Qt.
"""
from __future__ import annotations

from rostrum_gui.actions import Action

KINDS = ("mesh", "combine", "import", "group", "clay", "copies")      # what can be a body (the design note §1)
WORDS = {"falls": "Falls", "still": "Stays still", "off": "Off"}
BAR = "Simulate"
OP = "sim.body"


def at_top(doc, id_: str) -> bool:
    """The item sits in the scene's own list (its parent is the document), not inside a group, copies item or rig."""
    parent = doc.parent_of(id_)[0]
    return not parent or parent == doc.data.get("id")


def top_level(f) -> bool:
    return all(at_top(f.doc, i) for i in f.ids)


def kind_of(doc, ids: list[str]) -> str:
    """The picked items' one Simulate kind ("off" | "falls" | "still"), or "" when they differ or none can be a body."""
    kinds = {doc.item(i).get("simulate", "off") for i in ids if doc.has(i) and doc.item(i)["type"] in KINDS}
    return kinds.pop() if len(kinds) == 1 else ""


def calls(ids: list[str], kind: str) -> list[dict]:
    return [{"op": OP, "target": list(ids), "args": {"kind": kind}}]


def _valid(f) -> bool:
    return top_level(f) and not f.screen.get("paint")


DONE = {"falls": "{what} falls when simulated", "still": "{what} stays still when simulated", "off": "{what} is no longer simulated"}
ACTIONS = [
    Action(f"sim:{k}", WORDS[k], kinds=KINDS, min_targets=1, importance="secondary", rank=56 + n, group="simulate",
           panel=False, bar=BAR, valid=_valid, calls=lambda f, k=k: calls(f.ids, k), done=DONE[k],
           why="Simulate works on items in the scene's own list (shapes, combines, imports, groups, clay, copies); "
               "move an item out of its group first.")
    for n, k in enumerate(WORDS)
]
