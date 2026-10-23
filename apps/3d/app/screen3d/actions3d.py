"""Rostrum3D's action list, as plain data read into the kit's one list (rostrum_gui/actions.py): what the selection
allows, at the top of the settings panel (SPEC §3.3, "Combine: Union · Subtract · Intersect"). Only what applies is
offered (rule of individuality). Each action is one change made of operations an agent calls too (`combine.make`).
Today: Combine, on two or more solids (meshes or combines) in the same list; the first picked is the base, every
later one a cutter or partner. No Qt.
"""
from __future__ import annotations

from rostrum3d import fields as F
from rostrum3d.kind import KIND
from rostrum_core import ids
from rostrum_core.tree import index
from rostrum_gui.actions import Action, ActionList
from rostrum_gui.keymap import KeyMap

WORDS = {"union": "Union", "subtract": "Subtract", "intersect": "Intersect"}


class Facts:
    """The selection as the kit's guard reads it: `ids` in pick order (the base first), `items`, the document and the
    named truths an action's `when` reads."""

    def __init__(self, doc, selection: list[str]):
        self.doc, self.ids = doc, [i for i in selection if doc.has(i)]
        self.items = [doc.item(i) for i in self.ids]
        where = {doc.parent_of(i)[:2] for i in self.ids}
        self.facts = {"same_list": len(where) == 1, "solids": all(it["type"] in F.SOLIDS for it in self.items)}


def new_id(doc) -> str:
    return ids.counted(index(doc.data, KIND.lists), "combine")


def _make(op):
    return lambda f: [{"op": "combine.make", "target": list(f.ids), "args": {"op": op, "id": new_id(f.doc)}}]


ACTIONS = [
    Action(f"combine:{op}", WORDS[op], kinds=F.SOLIDS, min_targets=2, importance="primary", rank=5, group="shape",
           bar="Combine", when={"fact": "same_list"}, calls=_make(op), icon=op,
           why=f"{WORDS[op]} needs two or more solids (shapes or combines) in the same group, picked base first.")
    for op in F.COMBINE_OPS
]
LIST = ActionList(ACTIONS, KeyMap("Rostrum3D"), noun="solid")
