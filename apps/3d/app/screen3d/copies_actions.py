"""Copies and scatter on Rostrum3D's action list (brief 24), as plain data read into actions3d.LIST. Right-click a shape
(or a group, an import, a clay) › Make copies › Line · Grid · Circle · On a surface…; right-click a surface while
something else was selected › Scatter '<it>' on '<surface>'; right-click a copies item › Change near › Scale · Turn ·
Push · Colour. Each is one change made of the operations an agent calls too (copies.make, copies.scatter, effector.add).
The kit folds a bar's choices into a side menu (action_views.FOLD), so "Make copies" and "Change near" are one row each.

`facts.screen["scatter_from"]` is what was selected before the right-click on the surface (screen state: bridge3d's
openScatter; it ends at the next selection change). No Qt.
"""
from __future__ import annotations

from rostrum3d import copies_fields as CF, fields as F
from rostrum3d.kind import KIND
from rostrum_core import ids
from rostrum_core.tree import index
from rostrum_gui.actions import Action

from . import outline

MAKE, SCATTER, NEAR, HOLD, RELEASE = "copies.make", "copies.scatter", "effector.add", "copies.hold", "copies.release"
SOURCES = CF.SOURCES                                   # what a copies item can repeat
SURFACES = ("mesh", "combine", "import", "clay", "group")      # what copies can be scattered over
LAYOUT_WORDS = {"line": "Line", "grid": "Grid", "circle": "Circle", "surface": "On a surface…"}
NEAR_WORDS = {"scale": "Scale", "turn": "Turn", "push": "Push", "colour": "Colour"}
BALL = 0.05                                            # a new "near" sphere's radius, metres (small: it is a handle, not a thing)


def counted(doc, type_: str) -> str:
    return ids.counted(index(doc.data, KIND.lists), type_)


def make_calls(doc, targets: list[str], layout: str, surface: str = "") -> list[dict]:
    """copies.make (copies.scatter for a surface) on `targets`, the new item's id made fresh."""
    new = counted(doc, "copies")
    if surface:                                       # copies.scatter is copies.make with layout surface
        return [{"op": SCATTER, "target": list(targets), "args": {"id": new, "surface": surface}}]
    return [{"op": MAKE, "target": list(targets), "args": {"id": new, "layout": layout}}]


def _in_copies(f) -> bool:
    return any(f.doc.item(p)["type"] == "copies" for i in f.ids if (p := f.doc.parent_of(i)[0]) and f.doc.has(p))


def _make_valid(f) -> bool:
    # a copies item holds sources and effectors only: not another copies item; while painting the menu is Paint's;
    # never copies of the floor the scene stands on (a backdrop: start_scene.py)
    return not _in_copies(f) and not f.screen.get("paint") and not any(it.get("backdrop") for it in f.items)


def _scatter_sources(f) -> list[str]:
    """What was selected before the right-click on the surface: still there, repeatable, in one list, not the surface."""
    here = [i for i in f.screen.get("scatter_from", []) if f.doc.has(i)]
    if not here or len(f.ids) != 1 or f.ids[0] in here:
        return []
    from rostrum_core.tree import subtree_ids
    items = [f.doc.item(i) for i in here]
    if any(it["type"] not in SOURCES for it in items) or len({f.doc.parent_of(i)[:2] for i in here}) != 1:
        return []
    if any(f.ids[0] in subtree_ids(it, KIND.lists) for it in items):
        return []                                      # the surface is inside what would be copied
    if any(f.doc.item(p)["type"] == "copies" for i in here if (p := f.doc.parent_of(i)[0]) and f.doc.has(p)):
        return []
    return here


def _scatter_label(f) -> str:
    srcs = _scatter_sources(f)
    one = outline.label_of(f.doc.item(srcs[0])) if len(srcs) == 1 else f"{len(srcs)} items"
    return f"Scatter '{one}' on '{outline.label_of(f.items[0])}'"


def _near_pair(f):
    """(the copies item, the other selected item or None) when the selection is a copies item, alone or with one item
    beside it that is not part of it; else None."""
    copies = [i for i in f.items if i["type"] == "copies"]
    rest = [i for i in f.items if i["type"] != "copies"]
    if len(copies) != 1 or len(rest) > 1 or (rest and rest[0]["type"] not in F.ITEMS):
        return None
    if rest and f.doc.has(rest[0]["id"]):
        from rostrum_core.tree import subtree_ids
        if rest[0]["id"] in subtree_ids(copies[0], KIND.lists):
            return None
    return copies[0], (rest[0] if rest else None)


def reach(it: dict) -> float:
    """How far a change near reaches to start with: about two steps of the layout (metres)."""
    step = max(abs(it.get("spacingX", 0.0)), abs(it.get("spacingZ", 0.0))) if it.get("layout") in ("line", "grid") else \
        it.get("radius", 0.5) / 2 if it.get("layout") == "circle" else 0.25
    return round(max(0.1, 2 * step), 3)


def beside(it: dict) -> tuple[float, float, float]:
    """Where a new "near" sphere goes: by the middle of the copies' layout (the copies item's own place, in its list's
    space); the engine's own bounds are not asked for a handle this small."""
    x, y, z = (it.get(k, 0.0) for k in "xyz")
    n, lay = it.get("count", 1), it.get("layout")
    if lay == "line":
        x, y, z = (x + it.get("spacingX", 0.0) * (n - 1) / 2, y + it.get("spacingY", 0.0) * (n - 1) / 2,
                   z + it.get("spacingZ", 0.0) * (n - 1) / 2)
    elif lay == "grid":
        cols = max(1, it.get("columns", 4))
        rows = max(1, -(-n // cols))
        x, z = x + it.get("spacingX", 0.0) * (min(n, cols) - 1) / 2, z + it.get("spacingZ", 0.0) * (rows - 1) / 2
    # a little above, so it is seen and not inside a copy, but well within its starting reach: the copies by the middle
    # change at once (0.3 m above, with a reach of two steps, reached none of them)
    return round(x, 4), round(y + 0.6 * reach(it), 4), round(z, 4)


def near_calls(f, kind: str) -> list[dict]:
    pair = _near_pair(f)
    copies, other = pair
    eff = {"id": counted(f.doc, "effector"), "kind": kind, "radius": reach(copies)}
    out = []
    if other is None:                                  # a new small sphere to move: the change follows it
        ball = counted(f.doc, "mesh")
        x, y, z = beside(copies)
        args = {"id": ball, "shape": "sphere", "name": "Near", "radius": BALL, "x": x, "y": y, "z": z,
                "guide": True}                         # a handle in the view, never in the shot or a render
        parent = f.doc.parent_of(copies["id"])[0]
        if parent and f.doc.has(parent) and f.doc.item(parent)["type"] in F.HOLDERS:
            args["into"] = parent
        out.append({"op": "mesh.add", "args": args})
        eff["near"] = ball
    else:
        eff["near"] = other["id"]
    return out + [{"op": NEAR, "target": [copies["id"]], "args": eff}]


_SRC = dict(kinds=SOURCES, importance="secondary", group="copies", panel=False, valid=_make_valid, when={"fact": "same_list"},
            done="Made copies of {what}")
ACTIONS = [
    *(Action(f"copies:make:{lay}", LAYOUT_WORDS[lay], rank=50 + n, bar="Make copies",
             **({"do": "copies-surface"} if lay == "surface" else {"calls": (lambda f, lay=lay: make_calls(f.doc, f.ids, lay))}),
             why="Make copies works on shapes, groups, imports and clay in one list (not inside another copies item).", **_SRC)
      for n, lay in enumerate(LAYOUT_WORDS)),
    Action("copies:scatter", _scatter_label, kinds=SURFACES, max_targets=1, importance="secondary", rank=49, group="copies",
           panel=False, valid=lambda f: bool(_scatter_sources(f)), done="Scattered copies over the surface",
           calls=lambda f: make_calls(f.doc, _scatter_sources(f), "surface", f.ids[0]),
           why="Scatter needs something selected first, then a right-click on the surface to scatter it over."),
    *(Action(f"copies:near:{k}", NEAR_WORDS[k], min_targets=1, max_targets=2, importance="secondary", rank=60 + n,
             group="copies", panel=False, bar="Change near", valid=lambda f: _near_pair(f) is not None,
             calls=lambda f, k=k: near_calls(f, k),
             why="Change near works on a copies item (with one item beside it selected, the change follows that; "
                 "else a small sphere is added to move).")
      for n, k in enumerate(NEAR_WORDS)),
    Action("copies:release", "Release held copies", kinds=("copies",), max_targets=1, importance="secondary", rank=70,
           group="copies", panel=False, valid=lambda f: bool(f.items[0].get(CF.HELD)),
           calls=lambda f: [{"op": RELEASE, "target": list(f.ids), "args": {}}], done="Held copies back in their places",
           why="Release works on a copies item with a copy someone put by hand."),
]
