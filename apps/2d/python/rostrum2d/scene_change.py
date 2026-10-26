"""What Engine.load sends: the whole scene, or only what changed against the scene the engine holds (ENGINE_CONTRACT.md
§ 1 `change`). A node of the new description that is the very object (`is`) the held scene has with the same id, at
any place in the held tree (a layer moved into a group or out of one, or to another list, keeps its node), goes as its
id, a string: the engine keeps its own copy, whole subtree (it finds a kept id anywhere in what it holds). scene_keep.Keeper
makes descriptions that share those objects, wherever the item now sits; descriptions are never changed after they
are made, so the same object means the same node (and the same subtree: a node whose children moved is a new object).
The composition itself always goes whole.
"""
from __future__ import annotations

LISTS = ("layers", "effects", "masks", "rig", "stops")       # the child lists where an element may be a kept id


def _index(comp: dict) -> dict:
    """Every node of the tree under `comp` by id."""
    index, stack = {}, [comp]
    while stack:
        node = stack.pop()
        index[node["id"]] = node
        stack += [c for key in LISTS for c in node.get(key, [])]
    return index


def _with_refs(node: dict, held: dict) -> tuple[dict, int]:
    """`node` with each child (at any depth) that is a node of the held tree (`held`: its nodes by id) as its id;
    (it, how many kept)."""
    out, kept = node, 0
    for key in LISTS:
        kids = node.get(key)
        if not kids:
            continue
        new = []
        for kid in kids:
            if held.get(kid["id"]) is kid:
                new.append(kid["id"])
                kept += 1
            else:
                got, n = _with_refs(kid, held)
                new.append(got)
                kept += n
        if any(a is not b for a, b in zip(new, kids)):
            out = out if out is not node else dict(node)
            out[key] = new
    return out, kept


def request(held: dict | None, scene: dict) -> tuple[dict, str | None]:
    """The request that makes the engine hold `scene`: ({"change": …} or {"scene": …}, why it is a full load when a
    scene is held, else None)."""
    if held is None:
        return {"scene": scene}, None
    comp, kept = _with_refs(scene["comp"], _index(held["comp"]))
    if not kept:
        return {"scene": scene}, "no node of the new scene is one the engine holds"
    return {"change": {**scene, "comp": comp}}, None


def expand(change: dict, held: dict) -> dict:
    """The full scene a `change` stands for, given the held scene (what the engine does; a kept id that the held scene
    lacks raises KeyError)."""
    index = _index(held["comp"])

    def walk(node):
        if isinstance(node, str):
            return index[node]
        return {k: [walk(c) for c in v] if k in LISTS else v for k, v in node.items()}
    return {**change, "comp": walk(change["comp"])}
