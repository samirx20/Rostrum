"""Rostrum3D's action list, as plain data read into the kit's one list (rostrum_gui/actions.py): what the selection
allows, at the top of the settings panel (SPEC §3.3, "Combine: Union · Subtract · Intersect"). Only what applies is
offered (rule of individuality). Each action is one change made of operations an agent calls too (`combine.make`).
Today: Combine, on two or more solids (meshes or combines) in the same list; the first picked is the base, every
later one a cutter or partner. And "Bevel too big · use 1.84 mm (the largest that fits)": when the engine refused an outline's bevel (text,
logo, drawing; SPEC §4.4), the largest bevel that fits, one click away (`mesh.set bevel`). No Qt.
"""
from __future__ import annotations

import re

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

    def __init__(self, doc, selection: list[str], fits: dict | None = None):
        self.doc, self.ids = doc, [i for i in selection if doc.has(i)]
        self.fits = fits or {}          # {item id: the largest bevel that fits, metres} from the engine's last refusal
        self.items = [doc.item(i) for i in self.ids]
        where = {doc.parent_of(i)[:2] for i in self.ids}
        self.facts = {"same_list": len(where) == 1, "solids": all(it["type"] in F.SOLIDS for it in self.items)}


# The core's refusal (extrude.cpp): "<id>.bevel: 0.01 m is too big for … Accepted: at most 0.00184 m for this outline"
# or "… Accepted: 0 (this outline is too thin for a bevel)".
_TOO_BIG = re.compile(r"([\w.-]+)\.bevel: [^:]*? m is too big for .*?Accepted: (?:at most )?([0-9.eE+-]+)")


def bevel_fits(line: str) -> dict:
    """{item id: largest bevel that fits (m)} read from an engine failure line; {} when it isn't a bevel refusal."""
    m = _TOO_BIG.search(line or "")
    return {m.group(1): float(m.group(2))} if m else {}


def _fit_label(f) -> str:
    v = f.fits[f.ids[0]]
    return f"Bevel too big · use {v * 1000:.2f} mm (the largest that fits)" if v > 0 else "Bevel too big · use none"


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
ACTIONS.append(Action(
    "bevel:fit", _fit_label, kinds=("mesh",), max_targets=1, importance="primary", rank=1, group="shape",
    valid=lambda f: f.ids[0] in f.fits,
    calls=lambda f: [{"op": "mesh.set", "target": [f.ids[0]], "args": {"bevel": round(f.fits[f.ids[0]], 6)}}],
    why="Offered when the engine refused a text's or logo's bevel as too big for its outline."))
LIST = ActionList(ACTIONS, KeyMap("Rostrum3D"), noun="solid")
