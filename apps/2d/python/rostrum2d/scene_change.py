"""What Engine.load sends: the whole scene, or only what changed against the scene the engine holds (ENGINE_CONTRACT.md
§ 1 `change`). A node of the new description that is the very object (`is`) the held scene has with the same id at
the same place (the same list of the same parent) goes as its id, a string: the engine keeps its own copy, whole
subtree. scene_keep.Keeper makes descriptions that share those objects; descriptions are never changed after they
are made, so the same object means the same node. The composition itself always goes whole.
"""
from __future__ import annotations

LISTS = ("layers", "effects", "masks", "rig", "stops")       # the child lists where an element may be a kept id


def _with_refs(node: dict, held: dict) -> tuple[dict, int]:
    """`node` with each child that is `held`'s own child (same id, same list) as its id; (it, how many kept)."""
    out, kept = node, 0
    for key in LISTS:
        kids = node.get(key)
        if not kids:
            continue
        was = {c["id"]: c for c in held.get(key, [])}
        new = []
        for kid in kids:
            old = was.get(kid["id"])
            if old is kid:
                new.append(kid["id"])
                kept += 1
            elif old is not None:
                got, n = _with_refs(kid, old)
                new.append(got)
                kept += n
            else:
                new.append(kid)
        if any(a is not b for a, b in zip(new, kids)):
            out = out if out is not node else dict(node)
            out[key] = new
    return out, kept


def request(held: dict | None, scene: dict) -> tuple[dict, str | None]:
    """The request that makes the engine hold `scene`: ({"change": …} or {"scene": …}, why it is a full load when a
    scene is held, else None)."""
    if held is None:
        return {"scene": scene}, None
    comp, kept = _with_refs(scene["comp"], held["comp"])
    if not kept:
        return {"scene": scene}, "no node of the new scene is one the engine holds"
    return {"change": {**scene, "comp": comp}}, None


def expand(change: dict, held: dict) -> dict:
    """The full scene a `change` stands for, given the held scene (what the engine does; a kept id that the held scene
    lacks raises KeyError)."""
    index, stack = {}, [held["comp"]]
    while stack:
        node = stack.pop()
        index[node["id"]] = node
        stack += [c for key in LISTS for c in node.get(key, [])]

    def walk(node):
        if isinstance(node, str):
            return index[node]
        return {k: [walk(c) for c in v] if k in LISTS else v for k, v in node.items()}
    return {**change, "comp": walk(change["comp"])}
